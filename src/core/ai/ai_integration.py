"""
AI Integration Module for TenderTracker
Extends local LLM capabilities throughout the application with smart filtering,
risk assessment, natural language search, document summarization, and recommendations.
"""

import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

import db
import llm
import logger
from llm_client import LMStudioClient, ClassificationResult


class RiskAssessment(BaseModel):
    """Risk assessment for a tender."""
    bid_no: str = Field(description="Bid number")
    risk_level: str = Field(description="Risk level: Low, Medium, High, Critical")
    risk_score: float = Field(description="Risk score from 0.0 to 1.0")
    risk_factors: List[str] = Field(description="List of identified risk factors")
    mitigation_suggestions: List[str] = Field(description="Suggestions to mitigate risks")
    confidence: float = Field(description="Confidence in the assessment")


class TenderSummary(BaseModel):
    """AI-generated summary of a tender."""
    bid_no: str = Field(description="Bid number")
    executive_summary: str = Field(description="2-3 sentence executive summary")
    key_requirements: List[str] = Field(description="Key requirements and deliverables")
    evaluation_criteria: List[str] = Field(description="Evaluation criteria")
    timeline: str = Field(description="Timeline summary")
    budget_indicators: str = Field(description="Budget and financial indicators")


class BidRecommendation(BaseModel):
    """AI recommendation for bidding on a tender."""
    bid_no: str = Field(description="Bid number")
    recommend: bool = Field(description="Whether to recommend bidding")
    recommendation_score: float = Field(description="Score from 0.0 to 1.0")
    pros: List[str] = Field(description="Pros of bidding")
    cons: List[str] = Field(description="Cons of bidding")
    strategic_fit: str = Field(description="Strategic fit assessment")
    competitive_advantage: str = Field(description="Competitive advantage analysis")
    suggested_bid_price: Optional[str] = Field(description="Suggested bid price range")


class NaturalLanguageQueryResult(BaseModel):
    """Result of natural language query processing."""
    query: str = Field(description="Original query")
    interpreted_filters: Dict[str, Any] = Field(description="Interpreted search filters")
    search_terms: List[str] = Field(description="Extracted search terms")
    category_focus: Optional[str] = Field(description="Identified category focus")
    value_range: Optional[Tuple[float, float]] = Field(description="Interpreted value range")
    location_focus: Optional[str] = Field(description="Identified location focus")


class AIIntegration:
    """
    Main AI integration class providing enhanced AI capabilities.
    """
    
    def __init__(self):
        self.client = None
        self._ensure_client()
    
    def _ensure_client(self):
        """Ensure LLM client is initialized."""
        if self.client is None:
            self.client = LMStudioClient()
    
    async def close(self):
        """Close the LLM client."""
        if self.client:
            await self.client.close()
    
    async def assess_tender_risk(self, bid_obj: Dict[str, Any]) -> RiskAssessment:
        """
        Assess the risk level of a tender using AI.
        Considers financial requirements, timeline, technical complexity, and company fit.
        """
        self._ensure_client()
        bid_no = bid_obj.get("bid_no", "")
        
        # Get company profile for context
        profile = db.get_company_profile()
        
        system_prompt = (
            "You are a procurement risk analyst. Assess the risk level of the tender "
            "based on financial requirements, timeline, technical complexity, and company fit. "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        user_content = {
            "company_profile": {
                "categories": profile.get("categories", []),
                "max_est_value": profile.get("max_est_value", 0),
                "locations": profile.get("locations", "")
            },
            "tender": {
                "bid_no": bid_no,
                "items": bid_obj.get("items", ""),
                "category": bid_obj.get("category", ""),
                "est_value": bid_obj.get("est_value", ""),
                "emd": bid_obj.get("emd", ""),
                "epbg": bid_obj.get("epbg", ""),
                "min_turnover": bid_obj.get("min_turnover", ""),
                "exp_years": bid_obj.get("exp_years", ""),
                "contract_dur": bid_obj.get("contract_dur", ""),
                "location": bid_obj.get("location", ""),
                "end_date": bid_obj.get("end_date", "")
            }
        }
        
        prompt = (
            f"Tender & Profile:\n{json.dumps(user_content, indent=2)}\n\n"
            "Return a JSON object matching this schema exactly:\n"
            "{\n"
            "  \"bid_no\": \"str\",\n"
            "  \"risk_level\": \"str (Low/Medium/High/Critical)\",\n"
            "  \"risk_score\": float (0.0 to 1.0),\n"
            "  \"risk_factors\": [\"str\"],\n"
            "  \"mitigation_suggestions\": [\"str\"],\n"
            "  \"confidence\": float (0.0 to 1.0)\n"
            "}"
        )
        
        try:
            response = await self._call_llm(system_prompt, prompt)
            result = RiskAssessment(**response)
            
            # Cache the risk assessment
            db.upsert_tender_field(bid_no, "risk_assessment", json.dumps(result.model_dump()))
            
            logger.log("info", f"Risk assessment completed for {bid_no}: {result.risk_level}")
            return result
            
        except Exception as e:
            logger.log("err", f"Risk assessment failed for {bid_no}: {e}")
            # Return default risk assessment
            return RiskAssessment(
                bid_no=bid_no,
                risk_level="Medium",
                risk_score=0.5,
                risk_factors=["Unable to assess risk due to AI error"],
                mitigation_suggestions=["Manual review recommended"],
                confidence=0.0
            )
    
    async def generate_tender_summary(self, bid_obj: Dict[str, Any]) -> TenderSummary:
        """
        Generate an AI-powered summary of a tender.
        Provides executive summary, key requirements, evaluation criteria, and timeline.
        """
        self._ensure_client()
        bid_no = bid_obj.get("bid_no", "")
        
        system_prompt = (
            "You are a procurement analyst. Generate a concise summary of the tender "
            "highlighting key requirements, evaluation criteria, timeline, and budget indicators. "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        user_content = {
            "tender": {
                "bid_no": bid_no,
                "items": bid_obj.get("items", ""),
                "category": bid_obj.get("category", ""),
                "dept": bid_obj.get("dept", ""),
                "est_value": bid_obj.get("est_value", ""),
                "emd": bid_obj.get("emd", ""),
                "epbg": bid_obj.get("epbg", ""),
                "min_turnover": bid_obj.get("min_turnover", ""),
                "exp_years": bid_obj.get("exp_years", ""),
                "contract_dur": bid_obj.get("contract_dur", ""),
                "location": bid_obj.get("location", ""),
                "start_date": bid_obj.get("start_date", ""),
                "end_date": bid_obj.get("end_date", ""),
                "bid_opening": bid_obj.get("bid_opening", "")
            }
        }
        
        prompt = (
            f"Tender Details:\n{json.dumps(user_content, indent=2)}\n\n"
            "Return a JSON object matching this schema exactly:\n"
            "{\n"
            "  \"bid_no\": \"str\",\n"
            "  \"executive_summary\": \"str (2-3 sentences)\",\n"
            "  \"key_requirements\": [\"str\"],\n"
            "  \"evaluation_criteria\": [\"str\"],\n"
            "  \"timeline\": \"str\",\n"
            "  \"budget_indicators\": \"str\"\n"
            "}"
        )
        
        try:
            response = await self._call_llm(system_prompt, prompt)
            result = TenderSummary(**response)
            
            # Cache the summary
            db.upsert_tender_field(bid_no, "ai_summary", json.dumps(result.model_dump()))
            
            logger.log("info", f"Tender summary generated for {bid_no}")
            return result
            
        except Exception as e:
            logger.log("err", f"Tender summary failed for {bid_no}: {e}")
            # Return default summary
            return TenderSummary(
                bid_no=bid_no,
                executive_summary="Unable to generate summary due to AI error",
                key_requirements=["Manual review required"],
                evaluation_criteria=["See tender document"],
                timeline="See tender document",
                budget_indicators="See tender document"
            )
    
    async def generate_bid_recommendation(self, bid_obj: Dict[str, Any]) -> BidRecommendation:
        """
        Generate an AI-powered bid recommendation.
        Considers strategic fit, competitive advantage, and pros/cons analysis.
        """
        self._ensure_client()
        bid_no = bid_obj.get("bid_no", "")
        
        # Get company profile for context
        profile = db.get_company_profile()
        
        system_prompt = (
            "You are a procurement strategist. Analyze whether the company should bid on this tender "
            "considering strategic fit, competitive advantage, and potential risks. "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        user_content = {
            "company_profile": {
                "categories": profile.get("categories", []),
                "max_est_value": profile.get("max_est_value", 0),
                "locations": profile.get("locations", ""),
                "strengths": profile.get("strengths", "")
            },
            "tender": {
                "bid_no": bid_no,
                "items": bid_obj.get("items", ""),
                "category": bid_obj.get("category", ""),
                "est_value": bid_obj.get("est_value", ""),
                "emd": bid_obj.get("emd", ""),
                "min_turnover": bid_obj.get("min_turnover", ""),
                "exp_years": bid_obj.get("exp_years", ""),
                "location": bid_obj.get("location", ""),
                "end_date": bid_obj.get("end_date", "")
            }
        }
        
        prompt = (
            f"Company & Tender:\n{json.dumps(user_content, indent=2)}\n\n"
            "Return a JSON object matching this schema exactly:\n"
            "{\n"
            "  \"bid_no\": \"str\",\n"
            "  \"recommend\": bool,\n"
            "  \"recommendation_score\": float (0.0 to 1.0),\n"
            "  \"pros\": [\"str\"],\n"
            "  \"cons\": [\"str\"],\n"
            "  \"strategic_fit\": \"str\",\n"
            "  \"competitive_advantage\": \"str\",\n"
            "  \"suggested_bid_price\": \"str (optional)\"\n"
            "}"
        )
        
        try:
            response = await self._call_llm(system_prompt, prompt)
            result = BidRecommendation(**response)
            
            # Cache the recommendation
            db.upsert_tender_field(bid_no, "bid_recommendation", json.dumps(result.model_dump()))
            
            logger.log("info", f"Bid recommendation generated for {bid_no}: {result.recommend}")
            return result
            
        except Exception as e:
            logger.log("err", f"Bid recommendation failed for {bid_no}: {e}")
            # Return default recommendation
            return BidRecommendation(
                bid_no=bid_no,
                recommend=False,
                recommendation_score=0.0,
                pros=["Manual review required"],
                cons=["Unable to assess due to AI error"],
                strategic_fit="Unknown",
                competitive_advantage="Unknown"
            )
    
    async def process_natural_language_query(self, query: str) -> NaturalLanguageQueryResult:
        """
        Process a natural language query and extract structured search filters.
        Converts queries like "show me tenders under 10 lakhs in Delhi for electrical items"
        into structured filters.
        """
        self._ensure_client()
        
        system_prompt = (
            "You are a search query parser. Extract structured filters from natural language queries "
            "about tenders. Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = (
            f"Query: {query}\n\n"
            "Return a JSON object matching this schema exactly:\n"
            "{\n"
            "  \"query\": \"str\",\n"
            "  \"interpreted_filters\": {\n"
            "    \"category\": \"str (optional)\",\n"
            "    \"location\": \"str (optional)\",\n"
            "    \"max_value\": float (optional),\n"
            "    \"min_value\": float (optional),\n"
            "    \"keywords\": [\"str\"]\n"
            "  },\n"
            "  \"search_terms\": [\"str\"],\n"
            "  \"category_focus\": \"str (optional)\",\n"
            "  \"value_range\": [min, max] (optional),\n"
            "  \"location_focus\": \"str (optional)\"\n"
            "}"
        )
        
        try:
            response = await self._call_llm(system_prompt, prompt)
            result = NaturalLanguageQueryResult(**response)
            
            logger.log("info", f"Natural language query processed: {query}")
            return result
            
        except Exception as e:
            logger.log("err", f"Natural language query processing failed: {e}")
            # Return default result
            return NaturalLanguageQueryResult(
                query=query,
                interpreted_filters={"keywords": [query]},
                search_terms=[query],
                category_focus=None,
                value_range=None,
                location_focus=None
            )
    
    async def smart_filter_tenders(self, tenders: List[Dict[str, Any]], 
                                  criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Use AI to intelligently filter tenders based on complex criteria.
        Goes beyond simple keyword matching to understand context and relevance.
        """
        self._ensure_client()
        
        if not tenders:
            return []
        
        # Get company profile for relevance scoring
        profile = db.get_company_profile()
        
        system_prompt = (
            "You are a tender filtering assistant. Score each tender's relevance to the company "
            "based on the provided criteria. Return ONLY a valid JSON array of scores."
        )
        
        # Limit to 50 tenders per batch to avoid token limits
        batch_size = 50
        filtered_tenders = []
        
        for i in range(0, len(tenders), batch_size):
            batch = tenders[i:i + batch_size]
            
            tender_summaries = []
            for tender in batch:
                tender_summaries.append({
                    "bid_no": tender.get("bid_no", ""),
                    "items": tender.get("items", ""),
                    "category": tender.get("category", ""),
                    "est_value": tender.get("est_value", ""),
                    "location": tender.get("location", ""),
                    "dept": tender.get("dept", "")
                })
            
            prompt = (
                f"Company Profile:\n{json.dumps(profile, indent=2)}\n\n"
                f"Filter Criteria:\n{json.dumps(criteria, indent=2)}\n\n"
                f"Tenders:\n{json.dumps(tender_summaries, indent=2)}\n\n"
                "Return a JSON array where each element has:\n"
                "{\n"
                "  \"bid_no\": \"str\",\n"
                "  \"relevance_score\": float (0.0 to 1.0),\n"
                "  \"reason\": \"str\"\n"
                "}"
            )
            
            try:
                response = await self._call_llm(system_prompt, prompt)
                
                # Map scores back to tenders
                score_map = {item["bid_no"]: item for item in response}
                
                for tender in batch:
                    bid_no = tender.get("bid_no", "")
                    score_info = score_map.get(bid_no, {"relevance_score": 0.5, "reason": "Not scored"})
                    
                    tender["_ai_relevance_score"] = score_info["relevance_score"]
                    tender["_ai_relevance_reason"] = score_info["reason"]
                    
                    # Filter based on minimum relevance threshold
                    if score_info["relevance_score"] >= 0.3:
                        filtered_tenders.append(tender)
                
            except Exception as e:
                logger.log("err", f"Smart filtering batch failed: {e}")
                # Fall back to including all tenders in this batch
                filtered_tenders.extend(batch)
        
        # Sort by relevance score
        filtered_tenders.sort(key=lambda x: x.get("_ai_relevance_score", 0.5), reverse=True)
        
        logger.log("info", f"Smart filtering: {len(filtered_tenders)}/{len(tenders)} tenders passed")
        return filtered_tenders
    
    async def _call_llm(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """
        Internal method to call the LLM with proper error handling and retry logic.
        """
        url = f"{self.client.base_url}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.client.api_key}"
        }
        
        payload = {
            "model": self.client.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"}
        }
        
        retries = 3
        backoff = 1.0
        
        for attempt in range(retries):
            try:
                response = await self.client.client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                res_data = response.json()
                
                content = res_data["choices"][0]["message"]["content"]
                cleaned_json = llm.clean_json_response(content)
                return json.loads(cleaned_json)
                
            except Exception as e:
                err_str = str(e)
                if "json_object" in err_str and attempt == 0:
                    # Try without response_format for older servers
                    payload.pop("response_format", None)
                    continue
                
                logger.log("warn", f"LLM call failed (Attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
        
        raise Exception(f"Failed to call LLM after {retries} attempts")


# Global AI integration instance
_ai_integration = None


def get_ai_integration() -> AIIntegration:
    """Get the global AI integration instance."""
    global _ai_integration
    if _ai_integration is None:
        _ai_integration = AIIntegration()
    return _ai_integration


async def close_ai_integration():
    """Close the global AI integration instance."""
    global _ai_integration
    if _ai_integration:
        await _ai_integration.close()
        _ai_integration = None
