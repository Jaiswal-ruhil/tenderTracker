# FAISS Vector Indexing & Semantic Search module
try:
    import faiss
    _has_faiss = True
except Exception:
    faiss = None
    _has_faiss = False
import numpy as np
import json
import threading
import os
import re
try:
    from annoy import AnnoyIndex
    _has_annoy = True
except Exception:
    AnnoyIndex = None
    _has_annoy = False

# Local imports
import db
import llm
import logger

_lock = threading.Lock()
_embedder_paused = threading.Event()
_faiss_index = None
_bid_nos = []
_dimension = None

_embedder_running = False
_embedder_running_lock = threading.Lock()

def get_tender_embedding_text(rec):
    """
    Constructs a unified text description of a tender to generate its vector embedding.
    """
    items = rec.get("items") or ""
    cat = rec.get("category") or ""
    org = rec.get("organisation") or ""
    dept = rec.get("dept") or ""
    loc = rec.get("location") or ""
    comments = rec.get("comments") or ""
    return f"{items} {cat} {org} {dept} {loc} {comments}".strip()

def pause_background_embedder():
    """Pause background embedding while parse/fetch workers need the local LLM."""
    _embedder_paused.set()


def resume_background_embedder():
    """Resume background embedding after parse/fetch workers finish."""
    _embedder_paused.clear()


def rebuild_vector_index():
    """
    Loads all cached float embeddings from SQLite and builds the in-memory FAISS index.
    """
    global _faiss_index, _bid_nos, _dimension
    with _lock:
        try:
            if not _has_faiss and not _has_annoy:
                logger.log("warn", "No vector backend (FAISS or Annoy) available; skipping index build.")
                _faiss_index = None
                _bid_nos = []
                _dimension = None
                return False
            tenders = db.load_all_tenders(include_embeddings=True)
            # Filter for tenders that have a valid embedding float list
            embedded_tenders = [t for t in tenders if t.get("embedding") and isinstance(t["embedding"], list)]
            
            if not embedded_tenders:
                _faiss_index = None
                _bid_nos = []
                _dimension = None
                logger.log("info", "FAISS Vector Index: No tenders with cached embeddings found. Index is empty.")
                return False
                
            # Get dimension from first embedding
            _dimension = len(embedded_tenders[0]["embedding"])
            
            # Convert float lists to np.float32 array
            embeddings_array = np.array([t["embedding"] for t in embedded_tenders], dtype=np.float32)
            
            if _has_faiss:
                # Initialize FAISS index
                # FlatL2 is suitable for small-to-medium datasets (thousands of records)
                index = faiss.IndexFlatL2(_dimension)
                index.add(embeddings_array)
                _faiss_index = index
            else:
                # Build Annoy index as a fallback
                idx = AnnoyIndex(_dimension, 'euclidean')
                for i, vec in enumerate(embeddings_array.tolist()):
                    idx.add_item(i, vec)
                idx.build(10)
                _faiss_index = idx
            _bid_nos = [t["bid_no"] for t in embedded_tenders]
            logger.log("ok", f"FAISS Vector Index: Rebuilt index with {len(_bid_nos)} tenders (dimension {_dimension}).")
            return True
        except Exception as e:
            logger.log("err", f"FAISS Vector Index rebuild failed: {e}")
            _faiss_index = None
            _bid_nos = []
            _dimension = None
            return False

def semantic_search(query_text, limit=20):
    """
    Embeds the query text and retrieves nearest matching bid numbers sorted by similarity.
    Returns a list of tuples: (bid_no, distance)
    """
    if not query_text or not query_text.strip():
        return []
        
    global _faiss_index, _bid_nos, _dimension
    
    # Lazy build if index is not initialized
    if _faiss_index is None:
        rebuild_vector_index()
        
    if _faiss_index is None or not _bid_nos:
        return []
        
    try:
        # Load active LLM settings to call embedding API
        settings = db.load_settings()
        provider = settings.get("llm_provider", "Disabled")
        embed_model = settings.get("llm_embedding_model", "nomic-embed-text")
        if provider == "Disabled" or embed_model == "Disabled":
            logger.log("warn", "Semantic Search: LLM provider or embedding is disabled. Cannot get query embedding.")
            return []
            
        api_key = settings.get("llm_api_key", "")
        base_url = settings.get("llm_base_url", "")
        model = settings.get("llm_model", "")
        
        # Get query embedding
        query_vector = llm.get_embedding(query_text, provider, api_key, base_url, model)
        if not query_vector:
            return []
            
        # Verify query vector dimension matches index dimension
        if len(query_vector) != _dimension:
            logger.log("warn", f"Query embedding dimension {len(query_vector)} mismatch with index {_dimension}. Rebuilding index...")
            # Dimensions might mismatch if model settings changed; rebuild index with current models
            rebuild_vector_index()
            if _faiss_index is None or len(query_vector) != _dimension:
                return []
                
        results = []
        if _has_faiss:
            query_np = np.array([query_vector], dtype=np.float32)
            distances, indices = _faiss_index.search(query_np, min(limit, len(_bid_nos)))
            for dist, idx in zip(distances[0], indices[0]):
                if idx != -1 and idx < len(_bid_nos):
                    results.append((_bid_nos[idx], float(dist)))
        else:
            # Annoy fallback
            idxs, dists = _faiss_index.get_nns_by_vector(query_vector, n=min(limit, len(_bid_nos)), include_distances=True)
            for idx, dist in zip(idxs, dists):
                if idx != -1 and idx < len(_bid_nos):
                    results.append((_bid_nos[idx], float(dist)))
                
        # Return results sorted by distance ascending (nearest neighbor first)
        return results
    except Exception as e:
        logger.log("err", f"Semantic search failed: {e}")
        return []

def start_background_embedding_worker(callback_fn=None):
    """
    Spawns a background thread to generate embeddings for all tenders in SQLite
    that lack them, caching the results to SQLite. Rebuilds index when done.
    """
    global _embedder_running
    with _embedder_running_lock:
        if _embedder_running:
            logger.log("info", "Background Embedder: Worker thread is already active. Skipping duplicate spawn.")
            return
        
        # 1. Early exit if no vector backend is available to save resources
        if not _has_faiss and not _has_annoy:
            logger.log("info", "Background Embedder: No vector backend (FAISS or Annoy) available. Early exit.")
            return

        _embedder_running = True

    def worker():
        global _embedder_running
        try:
            # 2. Initial index build from already cached embeddings
            rebuild_vector_index()
            
            # 3. Check if LLM is enabled
            settings = db.load_settings()
            provider = settings.get("llm_provider", "Disabled")
            embed_model = settings.get("llm_embedding_model", "nomic-embed-text")
            if provider == "Disabled" or embed_model == "Disabled" or not settings.get("llm_use_embeddings", False):
                return
                
            api_key = settings.get("llm_api_key", "")
            base_url = settings.get("llm_base_url", "")
            model = settings.get("llm_model", "")
            
            # 4. Find tenders missing embeddings (use include_embeddings=True to check cached ones)
            tenders = db.load_all_tenders(include_embeddings=True)
            missing = [t for t in tenders if not t.get("embedding")]
            if not missing:
                return
                
            logger.log("info", f"Background Embedder: Found {len(missing)} tenders missing embeddings. Processing...")
            
            updated_count = 0
            consecutive_failures = 0
            for i, t in enumerate(missing, 1):
                if consecutive_failures >= 3:
                    logger.log("warn", "Background Embedder: Too many consecutive failures. Suspending embedder for this session to prevent log/server spam.")
                    break
                while _embedder_paused.is_set():
                    import time
                    time.sleep(0.5)
                bid_no = t.get("bid_no")
                text = get_tender_embedding_text(t)
                if not text:
                    continue
                    
                try:
                    emb = llm.get_embedding(text, provider, api_key, base_url, model)
                    if emb:
                        db.upsert_tender_field(bid_no, "embedding", json.dumps(emb))
                        updated_count += 1
                        consecutive_failures = 0
                        if i % 25 == 0 or i == len(missing):
                            logger.log("info", f"Background Embedder: {i}/{len(missing)} processed ({updated_count} cached).")
                except Exception as ex:
                    err_msg = str(ex)
                    logger.log("warn", f"Background Embedder: Failed to embed tender {bid_no}: {ex}")
                    
                    suspend_keywords = [
                        "unexpected endpoint", "httperror 404", "httperror 405", 
                        "no models loaded", "model is known to be unavailable",
                        "known to be unavailable", "disabled",
                        "failed to load local model", "model not found",
                        "model_load_failed", "failed to load", "httperror 500",
                        "httperror 400", "bad request"
                    ]
                    if any(kw in err_msg.lower() for kw in suspend_keywords):
                        logger.log("warn", "Background Embedder: Local server configuration/endpoint error. Suspending background embedder immediately to prevent server spam.")
                        break
                        
                    consecutive_failures += 1
                    # Sleep briefly to avoid hammering the API if it's failing
                    import time
                    time.sleep(2)
                    
            if updated_count > 0:
                logger.log("ok", f"Background Embedder: Successfully generated and cached {updated_count} embeddings.")
                rebuild_vector_index()
                if callback_fn:
                    callback_fn()
        except Exception as e:
            logger.log("err", f"Background Embedder worker failed: {e}")
        finally:
            with _embedder_running_lock:
                _embedder_running = False
            
    threading.Thread(target=worker, daemon=True).start()
