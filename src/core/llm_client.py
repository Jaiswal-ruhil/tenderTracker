import asyncio
import hashlib
import json
import time
from typing import List, Optional
import httpx
from pydantic import BaseModel, Field

import db
import logger

class ClassificationResult(BaseModel):
    bid_no: str = Field(description="The Bid Number of the tender")
    category: str = Field(description="The primary product/service category")
    subcategory: str = Field(description="The subcategory of the tender")
    keywords: List[str] = Field(description="List of relevant search keywords")
    products: List[str] = Field(description="List of product names matching this bid")
    confidence: float = Field(description="Confidence rating from 0.0 to 1.0")
    summary: str = Field(description="Concise summary of the tender details")
    recommended: bool = Field(description="Whether to recommend bidding on this tender")

def calculate_bid_hash(bid_obj: dict) -> str:
    """
    Computes a stable SHA-256 hash of the tender fields to use as a cache key.
    """
    stable_dict = {
        "bid_no": bid_obj.get("bid_no", ""),
        "items": bid_obj.get("items", ""),
        "dept": bid_obj.get("dept", ""),
        "category": bid_obj.get("category", ""),
        "est_value": bid_obj.get("est_value", ""),
        "location": bid_obj.get("location", "")
    }
    serialized = json.dumps(stable_dict, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

class LMStudioClient:
    """
    Async client for local LM Studio inference serving google/gemma-4-12b-qat.
    """
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        settings = db.load_settings()
        # Fallback to local default LM Studio URL if not set
        self.base_url = (base_url or settings.get("llm_base_url") or "http://localhost:1234/v1").rstrip("/")
        self.model = model or settings.get("llm_model") or "google/gemma-4-12b-qat"
        self.api_key = settings.get("llm_api_key") or "lm-studio"
        
        # Build limits: pooled connection limits to prevent socket exhaustion
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
        self.client = httpx.AsyncClient(limits=limits, timeout=60.0)

    async def close(self):
        await self.client.aclose()

    async def classify_bid_async(self, bid_obj: dict, force: bool = False) -> ClassificationResult:
        """
        Classifies a single tender bid. Checks cache first unless force=True.
        """
        bid_no = bid_obj.get("bid_no")
        if not bid_no:
            raise ValueError("Tender object is missing required 'bid_no'")

        # 1. Hashing & Caching check
        cache_key = calculate_bid_hash(bid_obj)
        if not force:
            cached = db.get_cached_classification(cache_key)
            if cached:
                logger.log("info", f"Cache hit for bid {bid_no}")
                try:
                    return ClassificationResult(**cached)
                except Exception as ex:
                    logger.log("warn", f"Cached classification malformed for {bid_no}: {ex}")

        # 2. Extract company profile info for relevance reasoning
        profile = db.get_company_profile()

        # 3. Compact Prompts (System Prompt < 100 tokens)
        system_prompt = (
            "You are a procurement assistant. Classify the tender JSON object against the target categories. "
            "Return ONLY a valid JSON object matching the requested schema."
        )

        user_content = {
            "company_categories": profile.get("categories", []),
            "company_max_value": profile.get("max_est_value", 0),
            "tender": {
                "bid_no": bid_no,
                "items": bid_obj.get("items", ""),
                "category": bid_obj.get("category", ""),
                "dept": bid_obj.get("dept", ""),
                "est_value": bid_obj.get("est_value", ""),
                "location": bid_obj.get("location", "")
            }
        }
        
        prompt = (
            f"Tender & Profile:\n{json.dumps(user_content, indent=2)}\n\n"
            "Return a JSON object matching this schema exactly:\n"
            "{\n"
            "  \"bid_no\": \"str\",\n"
            "  \"category\": \"str\",\n"
            "  \"subcategory\": \"str\",\n"
            "  \"keywords\": [\"str\"],\n"
            "  \"products\": [\"str\"],\n"
            "  \"confidence\": float (0.0 to 1.0),\n"
            "  \"summary\": \"str\",\n"
            "  \"recommended\": bool\n"
            "}"
        )

        # 4. Request payload with structured JSON schema
        url = f"{self.base_url}/chat/completions"
        
        # Prefer structured JSON schema output for speed and grammar-based sampling constraints
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "ClassificationResult",
                "schema": ClassificationResult.model_json_schema()
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        retries = 3
        backoff = 1.0
        last_error = None

        for attempt in range(retries):
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
                "response_format": response_format
            }
            try:
                response = await self.client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                res_data = response.json()
                
                content = res_data["choices"][0]["message"]["content"]
                
                # Use standard parser helper to strip thinking tags if present
                import llm
                cleaned_json_str = llm.clean_json_response(content)
                parsed_json = json.loads(cleaned_json_str)

                # Ensure Pydantic validation passes
                result = ClassificationResult(**parsed_json)
                
                # Write to database classification table and cache table
                db.save_classification(result.model_dump())
                db.set_cached_classification(cache_key, result.model_dump())
                
                # Auto-update status remarks in bids/tenders table
                remarks_text = f"AI Classification: {result.category} / {result.subcategory}\nRelevance Score: {result.confidence}\nSummary: {result.summary}"
                db.upsert_tender_field(bid_no, "remarks", remarks_text)
                db.upsert_tender_field(bid_no, "is_want_derived", 1 if result.recommended else 0)

                logger.log("info", f"Successfully classified bid {bid_no} (Attempt {attempt + 1})")
                return result

            except Exception as e:
                last_error = e
                # Fall back to standard json_object if structured outputs type is not supported by older servers
                err_str = str(e)
                if response_format.get("type") == "json_schema" and ("400" in err_str or "response_format" in err_str or "json_schema" in err_str):
                    logger.log("info", "Inference server does not support type 'json_schema'. Falling back to 'json_object'...")
                    response_format = {"type": "json_object"}
                    # Re-run immediately without sleeping for this configuration fallback
                    continue
                
                logger.log("warn", f"LLM client classification failed (Attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(backoff)
                    backoff *= 2.0

        raise last_error or Exception("Failed to classify bid after max retries")

    async def classify_bids_batch(self, bids: List[dict], force: bool = False) -> List[ClassificationResult]:
        """
        Processes up to 10 bids concurrently using asyncio.gather.
        """
        # Enforce batch size constraint of 10
        chunks = [bids[i:i + 10] for i in range(0, len(bids), 10)]
        results = []

        for chunk in chunks:
            tasks = [self.classify_bid_async(bid, force=force) for bid in chunk]
            chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in chunk_results:
                if isinstance(res, Exception):
                    logger.log("err", f"Batch item processing failed: {res}")
                else:
                    results.append(res)
        return results
