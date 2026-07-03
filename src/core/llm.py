import json
import urllib.request
import urllib.error
import re
import logger

_loaded_local_models = set()
_failed_local_models = {}
_failed_local_service_urls = {}

def normalize_local_service_key(base_url):
    return (base_url or "http://localhost:1234").strip().rstrip("/")


def parse_response_error(response_text):
    """
    Detect structured error payloads returned by local LLM endpoints.
    """
    if not response_text or not isinstance(response_text, str):
        return None
    try:
        parsed = json.loads(clean_json_response(response_text))
        if isinstance(parsed, dict):
            if parsed.get("error"):
                return parsed["error"]
            if parsed.get("detail"):
                return parsed["detail"]
            if parsed.get("message"):
                return parsed["message"]
        return None
    except Exception:
        return None


def clean_json_response(text):
    """
    Extract the JSON object from the response string, stripping away
    markdown formatting or conversational filler if present.
    """
    text = text.strip()
    # Remove markdown code blocks if present
    if text.startswith("```"):
        # Remove opening ```json or ```
        text = re.sub(r"^```(?:json)?\s*", "", text)
        # Remove closing ```
        text = re.sub(r"\s*```$", "", text)
    
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        return text[start:end+1]
    return text

def normalize_local_service_roots(base_url):
    """Return candidate local service roots for LM Studio / Ollama endpoints."""
    base_url = (base_url or "http://localhost:1234").strip().rstrip("/")
    candidates = [base_url]

    if base_url.endswith("/api/v1"):
        candidates.append(base_url[:-7] or base_url)
        candidates.append(base_url[:-3])
        candidates.append(base_url[:-4])
    elif base_url.endswith("/v1"):
        candidates.append(base_url[:-3] or base_url)
        candidates.append(f"{base_url[:-3]}/api/v1")
        candidates.append(f"{base_url[:-3]}/api")
    elif base_url.endswith("/api"):
        candidates.append(base_url[:-4] or base_url)
        candidates.append(f"{base_url[:-4]}/v1")
        candidates.append(f"{base_url}/v1")
    else:
        candidates.append(f"{base_url}/v1")
        candidates.append(f"{base_url}/api/v1")
        candidates.append(f"{base_url}/api")

    return [c for c in dict.fromkeys(candidates) if c]


def try_local_endpoint(base_url, resources, api_key=None, method="GET", body=None, timeout=10):
    """Attempt each candidate local endpoint path until one succeeds."""
    if isinstance(resources, str):
        resources = [resources]
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    last_error = None
    try:
        import json as _json
    except Exception:
        _json = None
    # local JSON helper ensures we don't rely on module-level name being present

    def join_local_url(root, resource):
        root = root.rstrip("/")
        resource = resource.lstrip("/")
        lower_root = root.lower()
        lower_resource = resource.lower()
        for prefix in ["api/v1", "v1", "api"]:
            if lower_root.endswith(f"/{prefix}") and lower_resource.startswith(f"{prefix}/"):
                resource = resource[len(prefix) + 1:]
                break
        return f"{root}/{resource}"

    for root in normalize_local_service_roots(base_url):
        for resource in resources:
            url = join_local_url(root, resource)
            if _json is not None:
                try:
                    request_body = _json.dumps(body).encode("utf-8") if body is not None else None
                except Exception:
                    request_body = None
            else:
                try:
                    import json as _json_local
                    request_body = _json_local.dumps(body).encode("utf-8") if body is not None else None
                except Exception:
                    request_body = None
            try:
                req = urllib.request.Request(
                    url,
                    data=request_body,
                    headers=headers,
                    method=method
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return response.read().decode("utf-8"), url
            except urllib.error.HTTPError as e:
                try:
                    error_body = e.read().decode("utf-8")
                except Exception:
                    error_body = e.reason if hasattr(e, 'reason') else str(e)
                last_error = ValueError(f"Local endpoint {url} HTTPError {e.code}: {error_body}")
                continue
            except Exception as e:
                last_error = ValueError(f"Local endpoint {url} failed: {type(e).__name__}: {e}")
                continue
    if last_error:
        raise last_error
    raise ValueError("No local endpoint candidates available.")


def auto_load_local_model(base_url, model, api_key=None):
    """
    Automatically loads (for LM Studio) or pulls (for Ollama) the model on demand.
    """
    if not model:
        return

    base_url_key = normalize_local_service_key(base_url)
    cache_key = (base_url_key, model.strip())
    if cache_key in _loaded_local_models:
        return
    if cache_key in _failed_local_models:
        raise _failed_local_models[cache_key]
    if base_url_key in _failed_local_service_urls:
        raise _failed_local_service_urls[base_url_key]

    # Check if the model is already available via any local API root
    def list_models(url):
        try:
            req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
            if api_key:
                req.add_header("Authorization", f"Bearer {api_key}")
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = response.read().decode("utf-8")
                models_json = json.loads(res_data)
                return [m.get("id") for m in models_json.get("data", []) if m.get("id")]
        except Exception:
            return None

    for root in normalize_local_service_roots(base_url):
        models_url = f"{root.rstrip('/')}/models"
        loaded_models = list_models(models_url)
        if loaded_models is not None:
            if model in loaded_models or any(model in lm or lm in model for lm in loaded_models):
                logger.log("info", f"Model '{model}' is already available/loaded.")
                return
            break

    # Try loading in LM Studio across candidate resources
    load_resources = [
        "models/load",
        "api/models/load",
        "v1/models/load",
        "api/v1/models/load"
    ]
    for resource in load_resources:
        try:
            response_text, used_url = try_local_endpoint(
                base_url,
                resource,
                api_key,
                method="POST",
                body={"model": model},
                timeout=30
            )
            error_msg = parse_response_error(response_text)
            if error_msg:
                logger.log("info", f"LM Studio model load returned error response for {used_url}: {error_msg}. Trying other local server methods...")
                continue
            logger.log("ok", f"LM Studio model load response: {response_text[:200]}")
            _loaded_local_models.add(cache_key)
            return
        except Exception as e:
            logger.log("info", f"LM Studio load failed for resource {resource}: {e}. Trying other local server methods...")

    # 3. Try pulling in Ollama if available
    try:
        response_text, used_url = try_local_endpoint(
            base_url,
            "pull",
            api_key,
            method="POST",
            body={"name": model, "stream": False},
            timeout=120
        )
        error_msg = parse_response_error(response_text)
        if error_msg:
            logger.log("warn", f"Ollama model pull/load returned error response: {error_msg}")
        else:
            logger.log("ok", f"Ollama model pull/load response: {response_text[:200]}")
            return
    except Exception as e:
        logger.log("warn", f"Ollama model pull/load failed: {e}")

    error = ValueError(f"Failed to load local model '{model}' from {base_url}")
    _failed_local_models[cache_key] = error
    _failed_local_service_urls[base_url_key] = error
    raise error

def call_llm(prompt, provider, api_key, base_url, model, response_json=False):
    """
    Calls the LLM provider (Google AI Studio or LM Studio) with a prompt.
    Returns the raw string output.
    """
    if not provider or provider == "Disabled":
        raise ValueError("LLM provider is disabled.")

    if provider == "Google AI Studio (Gemini)":
        if not api_key:
            raise ValueError("Google AI Studio API Key is required.")
        
        # Use provided model or default to gemini-1.5-flash
        model_name = model.strip() if model else "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        
        body = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        if response_json:
            body["generationConfig"] = {
                "responseMimeType": "application/json"
            }
        
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST"
        )
    
    elif provider == "Local LLM (LM Studio / Ollama)":
        base_url_key = normalize_local_service_key(base_url)
        if base_url_key in _failed_local_service_urls:
            raise _failed_local_service_urls[base_url_key]

        # Automatically load model on demand
        try:
            auto_load_local_model(base_url, model, api_key)
        except Exception as e:
            logger.log("warn", f"Auto-loading model failed: {e}")

        model_name = model.strip() if model else "local-model"
        body = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1
        }
        if response_json:
            body["response_format"] = {"type": "json_object"}

        last_error = None
        for resource in ["chat/completions", "v1/chat/completions", "api/v1/chat/completions"]:
            try:
                response_text, used_url = try_local_endpoint(base_url, resource, api_key, method="POST", body=body, timeout=15)
                error_msg = parse_response_error(response_text)
                if error_msg:
                    last_error = ValueError(f"Local chat endpoint {used_url} error: {error_msg}")
                    logger.log("info", f"Local chat endpoint {used_url} returned error: {error_msg}. Trying next candidate...")
                    continue
                res_json = json.loads(response_text)
                try:
                    return res_json["choices"][0]["message"]["content"]
                except Exception:
                    return response_text
            except Exception as e:
                last_error = e
                continue
        if last_error:
            raise last_error
        raise ValueError("No local chat endpoint candidates available.")
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

    try:
        # Use a 15-second timeout for requests
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = response.read().decode("utf-8")
            res_json = json.loads(res_data)
            
            if provider == "Google AI Studio (Gemini)":
                try:
                    return res_json["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    raise ValueError(f"Unexpected response format from Gemini: {res_json}")
            else:
                try:
                    return res_json["choices"][0]["message"]["content"]
                except (KeyError, IndexError):
                    raise ValueError(f"Unexpected response format from OpenAI-compatible API: {res_json}")
                    
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            logger.log("err", f"LLM API HTTP Error {e.code}: {err_body}")
            raise ValueError(f"API Error ({e.code}): {err_body[:200]}")
        except Exception:
            raise ValueError(f"HTTP Error {e.code}: {e.reason}")
    except Exception as e:
        logger.log("err", f"LLM API connection failed: {e}")
        raise e

def test_llm_connection(provider, api_key, base_url, model):
    """
    Sends a test request to verify API settings.
    """
    prompt = "Respond with exactly the word OK. Do not add punctuation or details."
    try:
        res = call_llm(prompt, provider, api_key, base_url, model, response_json=False)
        if "ok" in res.strip().lower():
            return True, "Connection successful."
        else:
            return True, f"Connection succeeded but returned unexpected response: '{res[:100]}'"
    except Exception as e:
        return False, str(e)

def get_similar_past_examples(text, limit=3):
    """
    RAG Helper: Retrieves similar historically parsed/corrected tenders
    from the SQLite database using keyword overlap to use as few-shot examples.
    """
    try:
        import db
        all_recs = db.load_all_tenders()
        valid_recs = [r for r in all_recs if r.get("bid_no") and r.get("items") and r.get("category")]
        if not valid_recs:
            return ""
            
        words = set(re.findall(r"\b[a-z]{4,}\b", text.lower()))
        scored = []
        for r in valid_recs:
            r_text = f"{r.get('items', '')} {r.get('category', '')} {r.get('organisation', '')} {r.get('dept', '')}".lower()
            r_words = set(re.findall(r"\b[a-z]{4,}\b", r_text))
            score = len(words.intersection(r_words))
            scored.append((score, r))
            
        scored.sort(key=lambda x: x[0], reverse=True)
        top_recs = [item[1] for item in scored[:limit]]
        
        example_strs = []
        for idx, r in enumerate(top_recs, 1):
            ex_txt = f"Example {idx} (Reference from past mappings):\n"
            ex_json = {
                "bid_no": r.get("bid_no", ""),
                "bid_url": r.get("bid_url", ""),
                "ministry": r.get("ministry", ""),
                "dept": r.get("dept", ""),
                "organisation": r.get("organisation", ""),
                "office": r.get("office", ""),
                "category": r.get("category", ""),
                "items": r.get("items", ""),
                "quantity": r.get("quantity", ""),
                "location": r.get("location", ""),
                "contract_dur": r.get("contract_dur", ""),
                "est_value": r.get("est_value", ""),
                "eval_method": r.get("eval_method", ""),
                "bid_type": r.get("bid_type", ""),
                "bid_to_ra": r.get("bid_to_ra", ""),
                "emd": r.get("emd", ""),
                "epbg": r.get("epbg", ""),
                "mii": r.get("mii", ""),
                "mse_pref": r.get("mse_pref", ""),
                "mse_relax": r.get("mse_relax", ""),
                "startup_relax": r.get("startup_relax", ""),
                "min_turnover": r.get("min_turnover", ""),
                "exp_years": r.get("exp_years", ""),
                "bid_opening": r.get("bid_opening", ""),
                "start_date": r.get("start_date", ""),
                "end_date": r.get("end_date", "")
            }
            ex_txt += f"Parsed Output JSON:\n{json.dumps(ex_json, indent=2)}\n"
            example_strs.append(ex_txt)
        if example_strs:
            return "\nHere are some examples of successfully parsed tenders from database history for your reference:\n" + "\n".join(example_strs)
    except Exception as e:
        logger.log("warn", f"RAG past examples retrieval failed: {e}")
    return ""

def get_similar_category_examples(item_name, limit=5):
    """
    RAG Helper: Retrieves historically mapped/corrected item-to-category associations
    from the SQLite database using keyword overlap.
    """
    try:
        import db
        all_recs = db.load_all_tenders()
        valid_recs = [r for r in all_recs if r.get("items") and r.get("category")]
        if not valid_recs:
            return ""
            
        words = set(re.findall(r"\b[a-z]{3,}\b", item_name.lower()))
        scored = []
        for r in valid_recs:
            items_words = set(re.findall(r"\b[a-z]{3,}\b", r["items"].lower()))
            score = len(words.intersection(items_words))
            scored.append((score, r["items"], r["category"]))
            
        scored.sort(key=lambda x: x[0], reverse=True)
        seen = set()
        top_examples = []
        for score, items, cat in scored:
            if cat not in seen:
                seen.add(cat)
                top_examples.append(f'- Description: "{items}" -> Mapped Category: "{cat}"')
                if len(top_examples) >= limit:
                    break
        if top_examples:
            return "\nHere are some examples of verified category mappings from history:\n" + "\n".join(top_examples)
    except Exception as e:
        logger.log("warn", f"RAG category examples retrieval failed: {e}")
    return ""

def llm_parse_tender(text, provider, api_key, base_url, model):
    """
    Asks the LLM to parse a tender document text block into a structured JSON.
    """
    examples = get_similar_past_examples(text)
    prompt = f"""You are an expert Government of India GeM tender document parsing assistant.
Extract fields from the following raw tender document text.

You MUST return a JSON object with the following keys. Do NOT omit any keys; if a field is not found in the text, set it to "" or "N/A".
Required keys:
- "bid_no": The Bid Number (e.g. "GEM/2026/B/7711387" or similar format)
- "bid_url": The detail link (if present, or construct it using the trailing digits of bid_no as: "https://bidplus.gem.gov.in/showbidDocument/<digits>")
- "ministry": Ministry/State name (e.g. "Uttar Pradesh", "Ministry of Mines")
- "dept": Department name (e.g. "Uttar Pradesh Cooperative Sugar Factories Federation")
- "organisation": Organisation name (e.g. "N/A" or specific name)
- "office": Office name (e.g. "Lucknow")
- "category": Clean standard category representing the main item (e.g. "Motor", "Cable", "Oxygen", "Ni Screen", "Industrial Gas")
- "items": Details of items/specifications (e.g. "Refilling of Industrial Gases" or specific sizes/models)
- "quantity": Total quantity (as a number or description)
- "location": Consignee location/address including pincode if found (e.g. "276404, Kisan Mill, Azamgarh")
- "contract_dur": Contract duration (e.g. "90 Days" or "1 Year")
- "est_value": Estimated bid value in INR (e.g. "144000")
- "eval_method": Evaluation method (e.g. "Total value wise evaluation")
- "bid_type": Type of bid (e.g. "Two Packet Bid")
- "bid_to_ra": Bid to RA enabled (Yes/No)
- "emd": EMD required (Yes/No)
- "epbg": ePBG required (Yes/No)
- "mii": MII compliance (Yes/No)
- "mse_pref": MSE purchase preference (Yes/No)
- "mse_relax": MSE relaxation (Yes/No)
- "startup_relax": Startup relaxation (Yes/No)
- "min_turnover": Minimum average annual turnover (e.g. "1 Lakh" or "N/A")
- "exp_years": Years of past experience required (e.g. "2 Year" or "N/A")
- "bid_opening": Bid opening date/time (e.g. "06-07-2026 15:30:00")
- "start_date": Start/Dated date (e.g. "25-06-2026")
- "end_date": Bid end date/time (e.g. "06-07-2026 15:00:00")

Text to parse:
---
{text}
---
{examples}

Provide ONLY the valid JSON object in response.
"""
    try:
        response_text = call_llm(prompt, provider, api_key, base_url, model, response_json=True)
        cleaned_json_str = clean_json_response(response_text)
        parsed_dict = json.loads(cleaned_json_str)
        return parsed_dict
    except Exception as e:
        logger.log("err", f"LLM parsing failed: {e}")
        raise e

def llm_map_category(item_name, existing_categories, provider, api_key, base_url, model):
    """
    Classifies a raw item name into one of the existing standard categories, or
    suggests a clean category name if no match exists.
    """
    examples = get_similar_category_examples(item_name)
    prompt = f"""You are a Govt of India tender cataloging assistant.
Given the item description: "{item_name}"

Your goal is to map this description to one of the standard categories if applicable, OR suggest a concise, clean standard category name (in Title Case, e.g. "Electric Motor", "Armoured Cable") if none of the existing ones fit.

Existing standard categories:
{json.dumps(existing_categories, indent=2)}
{examples}

You MUST respond with a JSON object in this format:
{{
  "category": "Matched or Suggested Category Name"
}}

Provide ONLY the valid JSON object.
"""
    try:
        response_text = call_llm(prompt, provider, api_key, base_url, model, response_json=True)
        cleaned_json_str = clean_json_response(response_text)
        parsed = json.loads(cleaned_json_str)
        return parsed.get("category", "").strip()
    except Exception as e:
        logger.log("err", f"LLM category mapping failed: {e}")
        raise e

def suggest_category_keywords(item_name, provider, api_key, base_url, model):
    """
    Asks the LLM to suggest a short list of 3-6 concise keyword tokens
    that best identify the item description. Returns a list of keywords.
    """
    prompt = f"""You are given an item description from a government tender:
"{item_name}"

Suggest up to 6 short keyword tokens (single words or short phrases up to 3 words)
that best summarize this item for automated category mapping. Return a JSON
object exactly like: {"keywords": ["kw1", "kw2"]}
Provide only valid JSON in the response.
"""
    try:
        response_text = call_llm(prompt, provider, api_key, base_url, model, response_json=True)
        cleaned_json_str = clean_json_response(response_text)
        parsed = json.loads(cleaned_json_str)
        kws = parsed.get("keywords") or parsed.get("keyword") or []
        if isinstance(kws, str):
            # split by commas
            kws = [k.strip() for k in re.split(r"[,;\\n]", kws) if k.strip()]
        if not isinstance(kws, list):
            return []
        # normalize keywords to lowercase tokens
        cleaned = []
        for k in kws:
            kk = str(k).strip().lower()
            if kk and kk not in cleaned:
                cleaned.append(kk)
        return cleaned[:6]
    except Exception as e:
        logger.log("warn", f"LLM keyword suggestion failed: {e}")
        return []

def is_server_reachable(base_url, timeout=3):
    """Quick health check to see if the LM Studio / Ollama base URL responds."""
    if not base_url:
        return False
    try:
        try_local_endpoint(base_url, ["models", "chat/completions"], timeout=timeout)
        return True
    except Exception:
        return False


def ensure_server_running(base_url, start_cmd=None):
    """If server not reachable and a start_cmd is provided, attempt to run it."""
    if is_server_reachable(base_url):
        return True
    if not start_cmd:
        return False
    try:
        import subprocess
        subprocess.Popen(start_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import time
        for _ in range(6):
            if is_server_reachable(base_url, timeout=2):
                return True
            time.sleep(1)
    except Exception as e:
        logger.log("warn", f"Failed to start LLM server with start_cmd: {e}")
    return is_server_reachable(base_url)

def get_embedding(text, provider, api_key, base_url, model):
    """
    Generates a vector embedding for the given text using the configured LLM provider.
    Returns a list of floats (the embedding vector).
    """
    if not provider or provider == "Disabled":
        raise ValueError("LLM provider is disabled.")
        
    if provider == "Google AI Studio (Gemini)":
        if not api_key:
            raise ValueError("Google AI Studio API Key is required.")
        # Default embedding model for Gemini
        model_name = "text-embedding-004"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:embedContent?key={api_key}"
        body = {
            "content": {
                "parts": [{"text": text}]
            }
        }
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST"
        )
    elif provider == "Local LLM (LM Studio / Ollama)":
        base_url_key = normalize_local_service_key(base_url)
        if base_url_key in _failed_local_service_urls:
            raise _failed_local_service_urls[base_url_key]

        # Automatically load model on demand
        try:
            auto_load_local_model(base_url, model, api_key)
        except Exception as e:
            logger.log("warn", f"Auto-loading model failed: {e}")

        model_name = model.strip() if model else "local-model"
        body = {
            "model": model_name,
            "input": text
        }
        last_error = None
        for resource in [
            "api/v1/embeddings",
            "v1/embeddings",
            "api/v1/embed",
            "v1/embed",
            "embeddings",
            "api/embeddings",
            "embed",
            "api/embed"
        ]:
            try:
                response_text, used_url = try_local_endpoint(base_url, resource, api_key, method="POST", body=body, timeout=10)
                error_msg = parse_response_error(response_text)
                if error_msg:
                    last_error = ValueError(f"Local embedding endpoint {used_url} error: {error_msg}")
                    logger.log("info", f"Local embedding endpoint {used_url} returned error: {error_msg}. Trying next candidate...")
                    continue
                res_json = json.loads(response_text)
                if "data" in res_json:
                    data = res_json["data"]
                    if isinstance(data, list) and data:
                        first = data[0]
                        if isinstance(first, dict) and "embedding" in first:
                            return first["embedding"]
                        if all(isinstance(x, (int, float)) for x in data):
                            return data
                if "embedding" in res_json:
                    embedding = res_json["embedding"]
                    if isinstance(embedding, dict):
                        return embedding.get("values") or embedding.get("vector")
                    return embedding
                last_error = ValueError(f"Unexpected local embedding response from {used_url}: {res_json}")
                logger.log("info", f"Local embedding endpoint {used_url} returned unexpected response. Trying next candidate...")
                continue
            except Exception as e:
                last_error = e
                continue
        if last_error:
            raise last_error
        raise ValueError("No local embedding endpoint candidates available.")
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = response.read().decode("utf-8")
            res_json = json.loads(res_data)
            
            if provider == "Google AI Studio (Gemini)":
                return res_json["embedding"]["values"]
            else:
                # OpenAI-compatible /v1/embeddings
                return res_json["data"][0]["embedding"]
    except Exception as e:
        logger.log("err", f"Failed to get embedding: {e}")
        raise e
