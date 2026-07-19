"""
llm_agent.py
~~~~~~~~~~~~
Agentic tool-calling loop for GeM tender PDF parsing.

Workflow:
  1. Build initial messages with full PDF text
  2. POST to LM Studio /v1/chat/completions with tools=[...all schemas...]
  3. If response has tool_calls → execute each via tender_tools.execute_tool()
     and append results as "tool" role messages
  4. Loop back to step 2 until a final message (no tool_calls) or MAX_ITER
  5. Parse the final JSON into a TenderRecord dict
  6. Fallback to llm.llm_parse_tender() if agent fails

LM Studio must be running with a model that supports function/tool calling.
Gemma 4 (google/gemma-4-12b-qat) supports tool-calling natively.
"""

import json
import urllib.request
import urllib.error
import re
import logger

from tender_tools import TOOL_SCHEMAS, execute_tool

MAX_AGENT_ITERATIONS = 8

# ---------------------------------------------------------------------------
# System prompt for the agentic loop
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a Government of India GeM (Government e-Marketplace) tender document parsing assistant.

You have access to specialized Python extraction tools. Use them systematically to extract all fields from the provided tender PDF text.

CRITICAL PERFORMANCE REQUIREMENT: Keep your internal thinking/reasoning blocks (<think>...</think>) extremely concise (less than 1-2 sentences). Do NOT write long explanations or think aloud. Decide which tool to call and output the tool call immediately to minimize latency.

Recommended tool call sequence:
1. extract_bid_metadata        → bid_no, dates, est_value
2. extract_department_info     → ministry, dept, organisation, office
3. extract_item_details        → category, items, quantity, eval_method, bid_type
4. extract_eligibility_criteria → min_turnover, exp_years, MII, MSE flags
5. extract_financial_security  → EMD, ePBG
6. extract_consignee_location  → delivery address
7. (Optional) compare_with_previous_bid → detect deviations from past tenders
8. (Optional) lookup_product_match      → check company product eligibility

After calling the tools and collecting results, return a FINAL JSON object with ALL of these keys (use "" for missing values):
{
  "bid_no": "",
  "bid_url": "",
  "ministry": "",
  "dept": "",
  "organisation": "",
  "office": "",
  "category": "",
  "items": "",
  "quantity": "",
  "location": "",
  "contract_dur": "",
  "est_value": "",
  "eval_method": "",
  "bid_type": "",
  "bid_to_ra": "",
  "emd": "",
  "epbg": "",
  "mii": "",
  "mse_pref": "",
  "mse_relax": "",
  "startup_relax": "",
  "min_turnover": "",
  "exp_years": "",
  "bid_opening": "",
  "start_date": "",
  "end_date": ""
}

Return ONLY valid JSON in your final message. Do not add explanations."""



# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

def run_tender_agent(
    pdf_text: str,
    base_url: str,
    model: str,
    api_key: str = "",
    max_iterations: int = MAX_AGENT_ITERATIONS,
) -> dict:
    """
    Run the agentic tool-calling loop and return a TenderRecord dict.

    Args:
        pdf_text:       Full extracted PDF text (from pdf_extractor.extract_text)
        base_url:       LM Studio base URL (e.g. "http://localhost:1234")
        model:          Model name loaded in LM Studio
        api_key:        API key (or "lm-studio" / empty)
        max_iterations: Safety cap on the number of LLM roundtrips

    Returns:
        dict with parsed tender fields. Falls back to {} on complete failure.
    """
    base_url = (base_url or "http://localhost:1234").rstrip("/")
    model_name = (model or "local-model").strip()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key or 'lm-studio'}"
    }

    # Truncate very long PDFs to keep the context window manageable
    # (keep first 8000 chars which covers most GeM bid documents)
    truncated_text = pdf_text[:8000] if len(pdf_text) > 8000 else pdf_text

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Parse this GeM tender PDF text:\n\n{truncated_text}"}
    ]

    chat_url = _find_chat_url(base_url, headers)
    if not chat_url:
        logger.log("warn", "llm_agent: Could not find chat/completions endpoint. Aborting agent run.")
        return {}

    final_content = None

    for iteration in range(1, max_iterations + 1):
        logger.log("info", f"[Agent] Iteration {iteration}/{max_iterations}")

        payload = {
            "model": model_name,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto",
            "temperature": 0.0,
        }

        try:
            response_text = _post_json(chat_url, payload, headers, timeout=600)

        except Exception as e:
            logger.log("warn", f"[Agent] LM Studio request failed at iteration {iteration}: {e}")
            break

        try:
            res = json.loads(response_text)
        except Exception as e:
            logger.log("warn", f"[Agent] Failed to parse LM Studio response JSON: {e}")
            break

        choice = _get_choice(res)
        if not choice:
            logger.log("warn", "[Agent] No valid choice in LM Studio response.")
            break

        # ── Tool calls requested by the model ────────────────────────────────
        tool_calls = choice.get("message", {}).get("tool_calls") or []
        if tool_calls:
            # Append assistant message with tool_calls
            messages.append(choice["message"])

            for tc in tool_calls:
                tc_id = tc.get("id", f"call_{iteration}")
                tc_name = tc.get("function", {}).get("name", "")
                tc_args_raw = tc.get("function", {}).get("arguments", "{}")

                try:
                    tc_args = json.loads(tc_args_raw) if isinstance(tc_args_raw, str) else tc_args_raw
                except Exception:
                    tc_args = {}

                logger.log("info", f"[Agent] 🔧 LLM requested tool: {tc_name}")
                logger.log("info", f"[Agent]    Arguments: {json.dumps(tc_args, ensure_ascii=False)}")
                result_str = execute_tool(tc_name, tc_args)
                
                # Format a cleaner result preview (truncate if too long)
                preview = result_str
                if len(preview) > 300:
                    preview = preview[:297] + "..."
                logger.log("ok", f"[Agent]    Tool result: {preview}")
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": tc_name,
                    "content": result_str,
                })
            # Continue loop — let the model process tool results
            continue

        # ── Final answer (no tool calls) ─────────────────────────────────────
        content = choice.get("message", {}).get("content", "")
        if content:
            final_content = content
            break

    if final_content:
        return _parse_final_json(final_content)

    logger.log("warn", f"[Agent] Exhausted {max_iterations} iterations without a final answer.")
    return {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_chat_url(base_url: str, headers: dict) -> str | None:
    """Try candidate chat endpoint paths and return the first that responds."""
    candidates = [
        f"{base_url}/v1/chat/completions",
        f"{base_url}/api/v1/chat/completions",
        f"{base_url}/chat/completions",
    ]
    for url in candidates:
        try:
            probe = {
                "model": "probe",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1
            }
            res_text = _post_json(url, probe, headers, timeout=5)
            # Filter out responses that indicate unexpected/invalid endpoint
            low = res_text.lower()
            if "unexpected endpoint" in low or "unexpected method" in low or "unexpected endpoint or method" in low:
                continue
            try:
                json.loads(res_text)
            except Exception:
                continue
            return url
        except urllib.error.HTTPError as e:
            # 400 = endpoint exists but request is malformed — still valid
            if e.code == 400:
                try:
                    error_body = e.read().decode("utf-8")
                    low = error_body.lower()
                    if "unexpected endpoint" in low or "unexpected method" in low or "unexpected endpoint or method" in low:
                        continue
                except Exception:
                    pass
                return url
            continue
        except Exception:
            continue
    # Return the most likely default without confirmation
    return f"{base_url}/v1/chat/completions"


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 120) -> str:
    """POST a JSON payload and return the response text."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _get_choice(res_json: dict) -> dict | None:
    """Extract the first choice from an OpenAI-compatible response."""
    try:
        return res_json["choices"][0]
    except (KeyError, IndexError, TypeError):
        return None


def _parse_final_json(content: str) -> dict:
    """
    Extract and parse the JSON object from the model's final response.
    Strips <think> blocks and markdown code fences.
    """
    # Remove thinking blocks
    content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
    # Strip markdown fences
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    # Find outermost JSON object
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1:
        logger.log("warn", f"[Agent] No JSON object found in final content: {content[:200]}")
        return {}

    try:
        parsed = json.loads(content[start: end + 1])
        # Normalise — replace None with ""
        return {k: (v if v is not None else "") for k, v in parsed.items()}
    except Exception as e:
        logger.log("warn", f"[Agent] JSON parse error on final content: {e}")
        return {}
