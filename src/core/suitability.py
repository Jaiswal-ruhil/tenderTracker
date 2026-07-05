import json
import os
import sys

# Ensure core imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
import llm
import logger

def evaluate_tender_suitability(record: dict, profile: dict) -> dict:
    """
    Evaluates the suitability of a tender record against a company profile using LLM.
    Updates the database with the derived suitability flag and AI reasoning remarks.
    """
    bid_no = record.get("bid_no")
    if not bid_no:
        return {"success": False, "error": "Tender record is missing 'bid_no'"}
        
    settings = db.load_settings()
    provider = settings.get("llm_provider", "Disabled")
    if not provider or provider == "Disabled":
        return {"success": False, "error": "LLM provider is disabled. Please configure LLM settings first."}
        
    api_key = settings.get("llm_api_key", "")
    base_url = settings.get("llm_base_url", "")
    model = settings.get("llm_model", "")
    
    # Construct LLM evaluation prompt
    prompt = f"""You are an expert procurement and tender evaluation analyst.
Your task is to assess whether the following tender is suitable for our company, based on our Company Profile and the Tender Details.

### Company Profile (Our capabilities & limits):
- Target Categories: {json.dumps(profile.get("categories", []))}
- Maximum Bidding Value (INR): {profile.get("max_est_value", 0)} (0 means no limit)
- Maximum EMD Budget (INR): {profile.get("max_emd", -1)} (-1 means no limit, 0 means no EMD is allowed)
- Minimum Experience We Have (Years): {profile.get("min_exp_years", 0)}
- Minimum Annual Turnover We Have (INR): {profile.get("min_turnover", 0)}
- Preferred/Serviceable Locations: {json.dumps(profile.get("location_keywords", []))} (empty list means all locations)
- MSE Registered: {"Yes" if profile.get("is_mse") else "No"}
- Startup India Registered: {"Yes" if profile.get("is_startup") else "No"}

### Tender Details:
- Bid Number: {record.get("bid_no")}
- Items Description: {record.get("items", "N/A")}
- Category: {record.get("category", "N/A")}
- Estimated Bid Value (INR): {record.get("est_value", "N/A")}
- EMD Required: {record.get("emd", "N/A")}
- ePBG Required: {record.get("epbg", "N/A")}
- Minimum Turnover Required: {record.get("min_turnover", "N/A")}
- Past Experience Required (Years): {record.get("exp_years", "N/A")}
- MSE Preference: {record.get("mse_pref", "N/A")}
- MSE Relaxation: {record.get("mse_relax", "N/A")}
- Startup Relaxation: {record.get("startup_relax", "N/A")}
- Consignee/Delivery Location: {record.get("location", "N/A")}

### Rules for Assessment:
1. **Category Match**: Does the tender Category or Items Description relate to our Target Categories?
2. **Estimated Value**: If Estimated Bid Value is available, does it exceed our Maximum Bidding Value (if limit is > 0)?
3. **EMD Budget**: If EMD is required, check if it exceeds our Maximum EMD Budget. Note that if we are MSE or Startup, and MSE Relaxation/Startup Relaxation is "Yes", EMD is often waived.
4. **Experience Criteria**: Check if past experience required exceeds what we have. If MSE Relaxation or Startup Relaxation is "Yes", and we are MSE/Startup, evaluate if we can be relaxed from experience requirements.
5. **Turnover Criteria**: Check if minimum turnover required exceeds what we have. Relaxations for MSE/Startup also apply here.
6. **Location Preference**: If we have location keywords specified, is the delivery location in our serviceable area?

You MUST respond with a JSON object in this format:
{{
  "suitable": true or false,
  "reasoning": "Clear, detailed breakdown of the decision, mentioning specific parameters (e.g. why we qualified or why we were disqualified)."
}}

Provide ONLY the valid JSON object in response.
"""
    try:
        response_text = llm.call_llm(prompt, provider, api_key, base_url, model, response_json=True)
        cleaned_json_str = llm.clean_json_response(response_text)
        result = json.loads(cleaned_json_str)
        
        suitable = bool(result.get("suitable", False))
        reasoning = result.get("reasoning", "No reasoning provided.")
        
        # Update database fields
        db.upsert_tender_field(bid_no, "is_want_derived", suitable)
        
        # Format remarks to include suitability summary
        remarks_text = f"AI Suitability: {'SUITABLE' if suitable else 'NOT SUITABLE'}\nReason: {reasoning}"
        db.upsert_tender_field(bid_no, "remarks", remarks_text)
        
        return {
            "success": True,
            "bid_no": bid_no,
            "suitable": suitable,
            "reasoning": reasoning,
            "remarks": remarks_text
        }
    except Exception as e:
        logger.log_err(f"Failed to evaluate suitability for bid {bid_no}: {e}")
        return {"success": False, "error": str(e)}
