import json
import urllib.request
import urllib.error
import re
import threading
import logger

_loaded_local_models = set()
_failed_local_models = {}
_failed_local_service_urls = {}
_failed_local_embedding_services = set()
_local_llm_lock = threading.RLock()
_chat_route_cache = {}
_embed_route_cache = {}


def extract_thinking_block(text):
    """
    Extract model reasoning emitted inside <think>...</think> blocks.
    Returns a plain text string or an empty string when unavailable.
    """
    if not text or not isinstance(text, str):
        return ""
    matches = re.findall(r"<think>\s*([\s\S]*?)\s*</think>", text, flags=re.IGNORECASE)
    cleaned = [m.strip() for m in matches if m and m.strip()]
    return "\n\n".join(cleaned)

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
        # Some local servers (LM Studio earlier versions) return plain-text
        # error messages with HTTP 200 responses, e.g.:
        # "Unexpected endpoint or method. (POST /embed). Returning 200 anyway"
        if not response_text or not isinstance(response_text, str):
            return None
        low = response_text.lower()
        if "unexpected endpoint" in low or "unexpected endpoint or method" in low or "unexpected method" in low:
            # Return the short error line
            first_line = response_text.splitlines()[0].strip()
            return first_line
        # Also catch simple 'error:' or 'failed' markers
        m = re.search(r"error[:\s]+(.+)", response_text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None


def clean_json_response(text):
    """
    Extract the JSON object from the response string, stripping away
    markdown formatting, reasoning (thinking) process blocks, or conversational filler.
    """
    text = text.strip()
    # Remove reasoning/thinking blocks if present
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
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

    res = [c for c in dict.fromkeys(candidates) if c]
    # Prioritize /api/v1 and /api roots over /v1 and raw base URL
    res.sort(key=lambda x: (
        0 if x.endswith("/api/v1") else
        1 if x.endswith("/api") else
        2 if x.endswith("/v1") else
        3
    ))
    return res


def extract_local_chat_content(res_json):
    """Extract assistant text from OpenAI-compatible or LM Studio native v1 chat responses."""
    if not isinstance(res_json, dict):
        return None
    try:
        msg = res_json["choices"][0]["message"]
        content = msg.get("content")
        if content:
            return content
        # Fallback to thinking/reasoning content if content is empty
        thinking = msg.get("reasoning_content") or msg.get("thinking")
        if thinking:
            return thinking
    except (KeyError, IndexError, TypeError):
        pass
    
    output = res_json.get("output")
    if isinstance(output, list):
        parts = []
        reasoning_parts = []
        for item in output:
            if isinstance(item, dict):
                itype = item.get("type")
                icontent = item.get("content")
                if icontent:
                    if itype == "message":
                        parts.append(str(icontent))
                    elif itype == "reasoning":
                        reasoning_parts.append(str(icontent))
        if parts:
            return "\n".join(parts)
        if reasoning_parts:
            return "\n".join(reasoning_parts)
            
    if res_json.get("message"):
        return str(res_json["message"])
    return None



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
        combined = f"{root}/{resource}"
        # Collapse common accidental duplicate segments introduced by
        # combining roots and resources (e.g. /v1/api/v1, /v1/v1, /api/api)
        replacements = [
            ("/v1/api/v1", "/api/v1"),
            ("/api/v1/v1", "/api/v1"),
            ("/v1/v1", "/v1"),
            ("/api/api", "/api"),
            # If root ended with /v1 and resource starts with /api/... we
            # want to drop the intermediate /v1 so /v1/api/embeddings -> /api/embeddings
            ("/v1/api/", "/api/"),
            ("/v1/api", "/api"),
        ]
        for a, b in replacements:
            if a in combined:
                combined = combined.replace(a, b)
        return combined

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
                    response_text = response.read().decode("utf-8")
                    error_msg = parse_response_error(response_text)
                    if error_msg:
                        last_error = ValueError(f"Local endpoint {url} error: {error_msg}")
                        continue
                    return response_text, url
            except urllib.error.HTTPError as e:
                try:
                    error_body = e.read().decode("utf-8")
                except Exception:
                    error_body = e.reason if hasattr(e, 'reason') else str(e)
                last_error = ValueError(f"Local endpoint {url} HTTPError {e.code}: {error_body}")
                # Raise immediately for 400 (Bad Request) or 500 (Internal Server Error)
                # to prevent retrying invalid endpoints and masking the real error.
                if e.code in (400, 500):
                    raise last_error
                continue
            except Exception as e:
                last_error = ValueError(f"Local endpoint {url} failed: {type(e).__name__}: {e}")
                continue
    if last_error:
        raise last_error
    raise ValueError("No local endpoint candidates available.")


def unload_local_models(base_url, api_key=None):
    """
    Attempts to unload all loaded models from LM Studio / Ollama to free up memory.
    """
    base_url_key = normalize_local_service_key(base_url)
    
    with _local_llm_lock:
        # Clear caches
        _loaded_local_models.clear()
        _failed_local_models.clear()
        
        # 1. LM Studio native unload
        for root in normalize_local_service_roots(base_url):
            try:
                models_url = f"{root.rstrip('/')}/models"
                req = urllib.request.Request(models_url, headers={"Content-Type": "application/json"}, method="GET")
                if api_key:
                    req.add_header("Authorization", f"Bearer {api_key}")
                with urllib.request.urlopen(req, timeout=5) as response:
                    res_data = response.read().decode("utf-8")
                    models_json = json.loads(res_data)
                    model_list = models_json.get("data", [])
                    for m in model_list:
                        instance_id = m.get("id")
                        if instance_id:
                            for unload_path in ["api/v1/models/unload", "v1/models/unload", "models/unload"]:
                                try:
                                    unload_url = f"{root.rstrip('/')}/{unload_path}"
                                    unload_req = urllib.request.Request(
                                        unload_url,
                                        headers={"Content-Type": "application/json"},
                                        data=json.dumps({"instance_id": instance_id}).encode("utf-8"),
                                        method="POST"
                                    )
                                    if api_key:
                                        unload_req.add_header("Authorization", f"Bearer {api_key}")
                                    with urllib.request.urlopen(unload_req, timeout=5) as res:
                                        res.read()
                                except Exception:
                                    pass
            except Exception:
                pass
    
        # 2. Ollama unload (sending model request with keep_alive=0)
        try:
            for root in normalize_local_service_roots(base_url):
                try:
                    generate_url = f"{root.rstrip('/')}/generate"
                    unload_req = urllib.request.Request(
                        generate_url,
                        headers={"Content-Type": "application/json"},
                        data=json.dumps({"model": "local-model", "keep_alive": 0}).encode("utf-8"),
                        method="POST"
                    )
                    if api_key:
                        unload_req.add_header("Authorization", f"Bearer {api_key}")
                    with urllib.request.urlopen(unload_req, timeout=3) as res:
                        res.read()
                except Exception:
                    pass
        except Exception:
            pass
        
        logger.log("info", "Unloaded local LLM models.")


def auto_load_local_model(base_url, model, api_key=None):
    with _local_llm_lock:
        return _auto_load_local_model_impl(base_url, model, api_key)


def _auto_load_local_model_impl(base_url, model, api_key=None):
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
    def clean_model_name(name):
        if not name:
            return ""
        # Convert to lowercase and normalize slashes for Windows/Linux compatibility
        name = name.lower().strip().replace("\\", "/")
        # Strip common file extensions
        for ext in (".gguf", ".bin", ".zip", ".tar.gz"):
            if name.endswith(ext):
                name = name[:-len(ext)]
        # Strip trailing tag (e.g. :latest or :2 or :qat)
        name = re.sub(r':[^:]+$', '', name)
        # Get the basename (the filename after the last slash)
        if "/" in name:
            name = name.split("/")[-1]
        return name.strip()

    def list_models(url):
        try:
            req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
            if api_key:
                req.add_header("Authorization", f"Bearer {api_key}")
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = response.read().decode("utf-8")
                models_json = json.loads(res_data)
                if not isinstance(models_json, dict):
                    return None
                # Handle OpenAI /v1/models format
                if "data" in models_json and isinstance(models_json["data"], list):
                    return [m.get("id") for m in models_json["data"] if m.get("id")]
                # Handle LM Studio native /api/v1/models format
                elif "models" in models_json and isinstance(models_json["models"], list):
                    return [
                        m.get("key") or m.get("id")
                        for m in models_json["models"]
                        if (m.get("key") or m.get("id")) and len(m.get("loaded_instances", [])) > 0
                    ]
                return None
        except Exception:
            return None

    for root in normalize_local_service_roots(base_url):
        models_url = f"{root.rstrip('/')}/models"
        loaded_models = list_models(models_url)
        if loaded_models is not None:
            clean_tgt = clean_model_name(model)
            cleaned_loaded = [clean_model_name(lm) for lm in loaded_models]
            if clean_tgt in cleaned_loaded or any(clean_tgt in cl or cl in clean_tgt for cl in cleaned_loaded):
                logger.log("info", f"Model '{model}' is already available/loaded.")
                _loaded_local_models.add(cache_key)
                return
            break

    # Get maximum parallel slots configuration
    import db
    settings = db.load_settings()
    parallel_val = settings.get("llm_max_parallel", 8)

    # Try loading in LM Studio across candidate resources (prefer native v1 API)
    load_resources = [
        "api/v1/models/load",
        "v1/models/load",
        "models/load",
        "api/models/load",
        # LM Studio also exposes model download endpoints; include them
        "models/download",
        "api/models/download",
        "api/v1/models/download",
    ]
    for resource in load_resources:
        try:
            bodies = [
                # Preference 1: Flat properties (Modern API / lms compatible)
                {
                    "model": model,
                    "gpu": "max",
                    "parallel": parallel_val,
                    "n_parallel": parallel_val,
                    "flash_attention": True,
                    "offload_kv_cache_to_gpu": True
                },
                # Preference 2: Nested config properties (Classic SDK compatible)
                {
                    "model": model,
                    "config": {
                        "parallel": parallel_val,
                        "n_parallel": parallel_val,
                        "gpu": "max"
                    }
                },
                # Preference 3: Safe fallback (Minimal request)
                {
                    "model": model
                }
            ]
            
            loaded_ok = False
            for body_candidate in bodies:
                try:
                    response_text, used_url = try_local_endpoint(
                        base_url,
                        resource,
                        api_key,
                        method="POST",
                        body=body_candidate,
                        timeout=30
                    )
                    error_msg = parse_response_error(response_text)
                    if error_msg:
                        logger.log("info", f"LM Studio load attempt with body {list(body_candidate.keys())} returned error response: {error_msg}. Trying next candidate...")
                        continue
                    
                    logger.log("ok", f"LM Studio model load response: {response_text[:200]}")
                    _loaded_local_models.add(cache_key)
                    loaded_ok = True
                    break
                except Exception as ex:
                    if body_candidate == bodies[-1]:
                        raise ex
                    logger.log("info", f"LM Studio load attempt with body {list(body_candidate.keys())} failed: {ex}. Trying next candidate...")
                    continue
                    
            if loaded_ok:
                return
        except Exception as e:
            if "model_load_failed" in str(e):
                raise e
            logger.log("info", f"LM Studio load failed for resource {resource}: {e}. Trying other local server methods...")
    # 3. Try model download endpoints (LM Studio v1 supports /api/v1/models/download)
    download_resources = [
        "models/download",
        "api/models/download",
        "api/v1/models/download",
    ]
    for resource in download_resources:
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
                logger.log("info", f"LM Studio model download returned error response for {used_url}: {error_msg}. Trying other local server methods...")
                continue
            # If the download API returns an immediate success, treat as loaded
            try:
                dt = json.loads(response_text)
            except Exception:
                dt = None
            # If a job id is provided, poll the download status endpoint
            job_id = None
            if isinstance(dt, dict):
                job_id = dt.get("job_id") or dt.get("id") or dt.get("task_id")
                if dt.get("status") in ("success", "completed", "ok"):
                    logger.log("ok", f"LM Studio model download succeeded: {used_url}")
                    _loaded_local_models.add(cache_key)
                    return
            if job_id:
                # Poll status
                import time
                status_resource_template = "models/download/status/{job_id}"
                for _ in range(20):
                    try:
                        stat_text, stat_url = try_local_endpoint(base_url, status_resource_template.format(job_id=job_id), api_key, method="GET", timeout=10)
                        stat_err = parse_response_error(stat_text)
                        if stat_err:
                            logger.log("info", f"Model download status {stat_url} returned error: {stat_err}")
                            break
                        try:
                            st = json.loads(stat_text)
                        except Exception:
                            st = None
                        if isinstance(st, dict) and st.get("status") in ("success", "completed", "ok"):
                            logger.log("ok", f"LM Studio model download completed: {stat_url}")
                            _loaded_local_models.add(cache_key)
                            return
                    except Exception:
                        pass
                    time.sleep(1)
            # If we reached here and no job id or not completed, continue to next candidate
            continue
        except Exception as e:
            logger.log("info", f"LM Studio download failed for resource {resource}: {e}. Trying other local server methods...")
            continue

    # 4. Try pulling in Ollama if available
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


def _build_local_chat_body(style, model_name, prompt, response_json=False, max_tokens=None):
    if style == "native":
        body = {
            "model": model_name,
            "input": prompt,
            "temperature": 0.1,
            "store": False,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
    else:
        body = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
    return body



def _local_chat_request(prompt, base_url, model, api_key, response_json=False, timeout=600, max_tokens=None):
    """Internal local chat call with endpoint route caching."""
    base_url_key = normalize_local_service_key(base_url)
    if base_url_key in _failed_local_service_urls:
        raise _failed_local_service_urls[base_url_key]

    try:
        auto_load_local_model(base_url, model, api_key)
    except Exception as e:
        logger.log("warn", f"Auto-loading model failed: {e}")

    model_name = model.strip() if model else "local-model"
    cached = _chat_route_cache.get(base_url_key)
    if cached:
        body = _build_local_chat_body(cached["style"], model_name, prompt, response_json, max_tokens)
        try:
            response_text, used_url = try_local_endpoint(
                base_url, cached["resources"], api_key, method="POST", body=body, timeout=timeout
            )
            content = extract_local_chat_content(json.loads(response_text))
            if content is not None:
                return content
        except Exception as e:
            err_str = str(e)
            if "HTTPError 404" in err_str or "HTTPError 405" in err_str or "Unexpected endpoint" in err_str:
                _chat_route_cache.pop(base_url_key, None)
            else:
                raise

    chat_attempts = [
        (["api/v1/chat"], "native"),
        (["v1/chat/completions", "chat/completions", "api/v1/chat/completions"], "openai"),
        (["chat", "v1/chat", "api/chat"], "openai"),
    ]
    last_error = None
    for resources, style in chat_attempts:
        body = _build_local_chat_body(style, model_name, prompt, response_json, max_tokens)

        try:
            response_text, used_url = try_local_endpoint(
                base_url, resources, api_key, method="POST", body=body, timeout=timeout
            )
            res_json = json.loads(response_text)
            content = extract_local_chat_content(res_json)
            if content is not None:
                _chat_route_cache[base_url_key] = {"resources": resources, "style": style}
                logger.log("ok", f"Local chat route cached: {used_url}")
                return content
            last_error = ValueError(f"Unexpected local chat response from {used_url}: {res_json}")
        except Exception as e:
            last_error = e
            continue
    if last_error:
        raise last_error
    raise ValueError("No local chat endpoint candidates available.")


def _local_embed_request(text, base_url, model, api_key, timeout=60):
    """Internal local embedding call with endpoint route caching."""
    base_url_key = normalize_local_service_key(base_url)
    if base_url_key in _failed_local_service_urls:
        raise _failed_local_service_urls[base_url_key]
    if base_url_key in _failed_local_embedding_services:
        raise ValueError(f"Local embedding service is known to be unavailable for {base_url}")

    try:
        auto_load_local_model(base_url, model, api_key)
    except Exception as e:
        logger.log("warn", f"Auto-loading model failed: {e}")

    model_name = model.strip() if model else "local-model"
    body_variants = [
        {"model": model_name, "input": text},
        {"model": model_name, "inputs": [text]},
        {"model": model_name, "input": [text]},
        {"input": text},
        {"inputs": [text]},
    ]

    def parse_embedding_response(res_json, used_url):
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
        raise ValueError(f"Unexpected local embedding response from {used_url}: {res_json}")

    cached = _embed_route_cache.get(base_url_key)
    if cached:
        resource = cached["resource"]
        for bvar in body_variants[: cached.get("variant_count", 1)]:
            try:
                response_text, used_url = try_local_endpoint(
                    base_url, resource, api_key, method="POST", body=bvar, timeout=timeout
                )
                return parse_embedding_response(json.loads(response_text), used_url)
            except Exception as e:
                err_str = str(e)
                if "HTTPError 404" in err_str or "HTTPError 405" in err_str or "Unexpected endpoint" in err_str:
                    _embed_route_cache.pop(base_url_key, None)
                    break
                else:
                    raise

    embed_resources = [
        "v1/embeddings",
        "api/v1/embeddings",
        "api/embeddings",
        "embeddings",
        "v1/embed",
        "api/v1/embed",
    ]
    last_error = None
    for resource in embed_resources:
        for idx, bvar in enumerate(body_variants):
            try:
                response_text, used_url = try_local_endpoint(
                    base_url, resource, api_key, method="POST", body=bvar, timeout=timeout
                )
                embedding = parse_embedding_response(json.loads(response_text), used_url)
                _embed_route_cache[base_url_key] = {"resource": resource, "variant_count": idx + 1}
                logger.log("ok", f"Local embedding route cached: {used_url}")
                return embedding
            except Exception as e:
                last_error = e
                continue
    if last_error:
        _failed_local_embedding_services.add(base_url_key)
        raise last_error
    _failed_local_embedding_services.add(base_url_key)
    raise ValueError("No local embedding endpoint candidates available.")


def prepare_local_llm(base_url, model, api_key=None):
    """
    Pre-load the local model and verify chat connectivity before batch work.
    Returns (success: bool, message: str).
    """
    if not model or not str(model).strip():
        return False, "No local model configured."
    with _local_llm_lock:
        _loaded_local_models.clear()
        _failed_local_models.clear()
        _failed_local_service_urls.clear()
        _failed_local_embedding_services.clear()
        _chat_route_cache.clear()
        _embed_route_cache.clear()
    try:
        auto_load_local_model(base_url, model, api_key)
        response = _local_chat_request(
            "Respond with exactly the word OK. Do not add punctuation or details.",
            base_url,
            model,
            api_key,
            response_json=False,
            timeout=120,
            max_tokens=5,
        )
        if "ok" in response.strip().lower():
            return True, "Local LLM ready."
        return True, f"Local LLM connected (unexpected probe response: '{response[:80]}')."
    except Exception as e:
        return False, str(e)


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
        p_lower = prompt.lower()
        if "category" in p_lower or "keyword" in p_lower:
            max_toks = 128
        else:
            max_toks = 1024
        return _local_chat_request(prompt, base_url, model, api_key, response_json, timeout=600, max_tokens=max_toks)
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
    if provider == "Local LLM (LM Studio / Ollama)":
        with _local_llm_lock:
            _loaded_local_models.clear()
            _failed_local_models.clear()
            _failed_local_service_urls.clear()
            _failed_local_embedding_services.clear()
            _chat_route_cache.clear()
            _embed_route_cache.clear()
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
    from parser import clean_raw_text
    text = clean_raw_text(text)
    examples = get_similar_past_examples(text)
    prompt = f"""You are an expert Government of India GeM tender document parsing assistant.
Extract fields from the following raw tender document text.

Anatomy of GeM Bid Number Pattern:
- GEM: The universal prefix for every official bid on the marketplace.
- YYYY: Represents the calendar year (e.g., 2026).
- B: Denotes standard public bidding.
- Unique ID sequence: An incremental sequence of digits (e.g. 7711387, or matching 7XXXXX6 ending with 6 for specific mat procurements).

You MUST return a JSON object with the following keys. Do NOT omit any keys; if a field is not found in the text, set it to "" or "N/A".
Required keys:
- "bid_no": The Bid Number (e.g. "GEM/2026/B/7711387" or wildcard formats like "GEM/2026/B/7XXXXX6")
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
        thinking = extract_thinking_block(response_text)
        cleaned_json_str = clean_json_response(response_text)
        parsed_dict = json.loads(cleaned_json_str)
        if thinking:
            parsed_dict["_llm_thinking"] = thinking
        return parsed_dict
    except Exception as e:
        logger.log("err", f"LLM parsing failed: {e}")
        raise e

def llm_parse_tender_agentic(text, provider, api_key, base_url, model):
    """
    Agentic tool-calling parser for GeM tender PDFs.

    Sends the PDF text to LM Studio with all 10 extraction tool schemas.
    The model decides which tools to call; results are fed back until the
    model produces a final TenderRecord JSON.

    Falls back to llm_parse_tender() if:
      - provider is not a local LLM
      - the agent returns an empty/incomplete record
      - any unexpected error occurs

    Only works with Local LLM (LM Studio / Ollama) since the agent needs
    direct tool-calling support. Google AI Studio does not expose the
    same /v1/chat/completions + tools interface locally.
    """
    if provider != "Local LLM (LM Studio / Ollama)":
        return llm_parse_tender(text, provider, api_key, base_url, model)

    try:
        import llm_agent
        result = llm_agent.run_tender_agent(
            pdf_text=text,
            base_url=base_url,
            model=model,
            api_key=api_key or "lm-studio",
        )
        # Validate: must have at minimum a bid_no
        if result and result.get("bid_no"):
            logger.log("info", f"[Agent] Agentic parse succeeded: {result.get('bid_no')}")
            return result
        else:
            logger.log("warn", "[Agent] Agentic parse returned incomplete result. Falling back to single-prompt LLM.")
    except Exception as e:
        logger.log("warn", f"[Agent] Agentic parse failed: {e}. Falling back to single-prompt LLM.")

    return llm_parse_tender(text, provider, api_key, base_url, model)


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
        import db
        settings = db.load_settings()
        embedding_model = settings.get("llm_embedding_model")
        if not embedding_model:
            # Avoid falling back to chat/generation models (like google/gemma-4-12b-qat) which are not suitable for embeddings
            if model and any(x in model.lower() for x in ["gemma", "llama", "qwen", "phi"]):
                embedding_model = "nomic-embed-text"
            else:
                embedding_model = model or "nomic-embed-text"
        return _local_embed_request(text, base_url, embedding_model, api_key, timeout=60)
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
