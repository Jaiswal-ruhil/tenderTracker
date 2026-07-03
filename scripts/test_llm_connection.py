import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'core'))

import db
import llm

def main():
    settings = db.load_settings()
    provider = settings.get("llm_provider", "Disabled")
    api_key = settings.get("llm_api_key", "")
    base_url = settings.get("llm_base_url", "")
    model = settings.get("llm_model", "")

    print(f"Testing LLM connection: provider={provider}, model={model}, base_url={base_url}")
    ok, msg = llm.test_llm_connection(provider, api_key, base_url, model)
    print("Result:", ok, msg)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print("LLM test failed:", e)
