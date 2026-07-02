import faiss
import numpy as np
import json
import threading
import os
import re

# Local imports
import db
import llm
import logger

_lock = threading.Lock()
_faiss_index = None
_bid_nos = []
_dimension = None

def get_tender_embedding_text(rec):
    """
    Constructs a unified text description of a tender to generate its vector embedding.
    """
    items = rec.get("items") or ""
    cat = rec.get("category") or ""
    org = rec.get("organisation") or ""
    dept = rec.get("dept") or ""
    loc = rec.get("location") or ""
    return f"{items} {cat} {org} {dept} {loc}".strip()

def rebuild_vector_index():
    """
    Loads all cached float embeddings from SQLite and builds the in-memory FAISS index.
    """
    global _faiss_index, _bid_nos, _dimension
    with _lock:
        try:
            tenders = db.load_all_tenders()
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
            
            # Initialize FAISS index
            # FlatL2 is suitable for small-to-medium datasets (thousands of records)
            index = faiss.IndexFlatL2(_dimension)
            index.add(embeddings_array)
            
            _faiss_index = index
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
        if provider == "Disabled":
            logger.log("warn", "Semantic Search: LLM provider is disabled. Cannot get query embedding.")
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
                
        # Query FAISS index
        query_np = np.array([query_vector], dtype=np.float32)
        distances, indices = _faiss_index.search(query_np, min(limit, len(_bid_nos)))
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
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
    def worker():
        try:
            # 1. Initial index build from already cached embeddings
            rebuild_vector_index()
            
            # 2. Check if LLM is enabled
            settings = db.load_settings()
            provider = settings.get("llm_provider", "Disabled")
            if provider == "Disabled":
                return
                
            api_key = settings.get("llm_api_key", "")
            base_url = settings.get("llm_base_url", "")
            model = settings.get("llm_model", "")
            
            # 3. Find tenders missing embeddings
            tenders = db.load_all_tenders()
            missing = [t for t in tenders if not t.get("embedding")]
            if not missing:
                return
                
            logger.log("info", f"Background Embedder: Found {len(missing)} tenders missing embeddings. Processing...")
            
            updated_count = 0
            for t in missing:
                bid_no = t.get("bid_no")
                text = get_tender_embedding_text(t)
                if not text:
                    continue
                    
                try:
                    emb = llm.get_embedding(text, provider, api_key, base_url, model)
                    if emb:
                        db.upsert_tender_field(bid_no, "embedding", json.dumps(emb))
                        updated_count += 1
                except Exception as ex:
                    logger.log("warn", f"Background Embedder: Failed to embed tender {bid_no}: {ex}")
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
            
    threading.Thread(target=worker, daemon=True).start()
