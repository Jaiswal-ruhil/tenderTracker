"""Configure the app to use a Local LLM (LM Studio / Ollama).

Usage:
    python scripts/config_llm_studio.py [base_url] [model]

Example:
    python scripts/config_llm_studio.py http://localhost:1234 google/gemma-4-12b-qat
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'core'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import db

def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:1234"
    model = sys.argv[2] if len(sys.argv) > 2 else "google/gemma-4-12b-qat"

    db.save_setting("llm_provider", "Local LLM (LM Studio / Ollama)")
    db.save_setting("llm_base_url", base_url)
    db.save_setting("llm_model", model)
    db.save_setting("llm_use_mapping", True)
    print(f"Saved LLM Studio settings: base_url={base_url}, model={model}")

if __name__ == '__main__':
    main()
