import json
import urllib.request
import urllib.error
import re
import logger

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

def auto_load_local_model(base_url, model, api_key=None):
    """
    Automatically loads (for LM Studio) or pulls (for Ollama) the model on demand.
    """
    if not model:
        return
        
    url_base = base_url.strip() if base_url else "http://localhost:1234/v1"
    url_base = url_base.rstrip("/")
    
    # 1. Clean server root
    server_root = url_base
    if server_root.endswith("/v1"):
        server_root = server_root[:-3]
        
    # Check currently loaded/available models via OpenAI-compatible endpoint
    models_url = f"{url_base}/models"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        
    try:
        req = urllib.request.Request(models_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = response.read().decode("utf-8")
            models_json = json.loads(res_data)
            loaded_models = [m.get("id") for m in models_json.get("data", []) if m.get("id")]
            # If our model is already loaded/available, we are good!
            if model in loaded_models or any(model in lm or lm in model for lm in loaded_models):
                logger.log("info", f"Model '{model}' is already available/loaded.")
                return
    except Exception as e:
        # If the models list check fails, we still proceed to attempt loading/pulling
        logger.log("warn", f"Could not check loaded models: {e}")
        
    # 2. Try loading in LM Studio
    # Endpoint: POST {server_root}/api/v1/models/load
    lm_studio_load_url = f"{server_root}/api/v1/models/load"
    try:
        body = {"model": model}
        req = urllib.request.Request(
            lm_studio_load_url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        logger.log("info", f"Attempting to load model '{model}' in LM Studio...")
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = response.read().decode("utf-8")
            logger.log("ok", f"LM Studio model load response: {res_data[:200]}")
            return
    except urllib.error.HTTPError as e:
        # If it's a 404 or other error, it might be Ollama or a different server version
        logger.log("info", f"LM Studio load endpoint returned HTTP status {e.code}. Checking if Ollama...")
    except Exception as e:
        logger.log("info", f"LM Studio load failed: {e}. Trying Ollama fallback...")

    # 3. Try pulling in Ollama
    # Endpoint: POST {server_root}/api/pull
    ollama_pull_url = f"{server_root}/api/pull"
    try:
        body = {"name": model, "stream": False}
        req = urllib.request.Request(
            ollama_pull_url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        logger.log("info", f"Attempting to pull/load model '{model}' in Ollama...")
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = response.read().decode("utf-8")
            logger.log("ok", f"Ollama model pull/load response: {res_data[:200]}")
            return
    except Exception as e:
        logger.log("warn", f"Ollama model pull/load failed: {e}")

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
        # Automatically load model on demand
        try:
            auto_load_local_model(base_url, model, api_key)
        except Exception as e:
            logger.log("warn", f"Auto-loading model failed: {e}")

        # Ensure base URL is set
        url_base = base_url.strip() if base_url else "http://localhost:1234/v1"
        url = url_base.rstrip("/")
        
        # Build chat completions URL
        if not url.endswith("/chat/completions"):
            if url.endswith("/v1"):
                url = f"{url}/chat/completions"
            else:
                url = f"{url}/v1/chat/completions"
        
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
            
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST"
        )
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
