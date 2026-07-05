import sys
import json
import traceback
import os

# Ensure we can import the project's src/ by adding its absolute path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)
CORE = os.path.join(SRC, 'core')
if CORE not in sys.path:
    sys.path.insert(0, CORE)
import llm

def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:1234"
    model = sys.argv[2] if len(sys.argv) > 2 else "google/gemma-4-12b-qat"
    provider = "Local LLM (LM Studio / Ollama)"
    api_key = ""  # adjust if your LM Studio requires a token

    print(f"Testing local LLM at {base_url} for model {model}")

    try:
        ok, msg = llm.test_llm_connection(provider, api_key, base_url, model)
        print("test_llm_connection:", ok, msg)
    except Exception as e:
        print("test_llm_connection raised:", e)
        traceback.print_exc()

    # Try auto-loading model explicitly
    try:
        print("Calling auto_load_local_model()...")
        llm.auto_load_local_model(base_url, model, api_key)
        print("auto_load_local_model: success (model considered loaded)")
    except Exception as e:
        print("auto_load_local_model failed:", e)
        traceback.print_exc()

    # Try a small embedding request
    try:
        print("Requesting embedding for short test string...")
        emb = llm.get_embedding("Hello from tenderTracker test", provider, api_key, base_url, model)
        print("Embedding returned length:", len(emb) if hasattr(emb, '__len__') else 'unknown')
        if hasattr(emb, '__iter__'):
            print("First 5 values:", list(emb)[:5])
    except Exception as e:
        print("get_embedding failed:", e)
        traceback.print_exc()

if __name__ == '__main__':
    main()
