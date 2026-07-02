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

def llm_parse_tender(text, provider, api_key, base_url, model):
    """
    Asks the LLM to parse a tender document text block into a structured JSON.
    """
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
    prompt = f"""You are a Govt of India tender cataloging assistant.
Given the item description: "{item_name}"

Your goal is to map this description to one of the standard categories if applicable, OR suggest a concise, clean standard category name (in Title Case, e.g. "Electric Motor", "Armoured Cable") if none of the existing ones fit.

Existing standard categories:
{json.dumps(existing_categories, indent=2)}

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
