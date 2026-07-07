import sys
import os
import json

# Add src and src/core to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "core")))

import pdf_extractor
import parser
import llm

def main():
    pdf_path = r"D:\gem tenders\GeM-Bidding-9246838.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return

    print(f"Reading PDF: {pdf_path}")
    pdf_bytes = open(pdf_path, "rb").read()
    text = pdf_extractor.extract_text(pdf_bytes)
    md_text = parser.convert_pdf_text_to_markdown(text)
    
    print("\nPDF converted to markdown. Length:", len(md_text))
    print("\nRunning agentic tool-calling parser...")
    
    # Configure provider
    provider = "Local LLM (LM Studio / Ollama)"
    base_url = "http://localhost:1234"
    model = "google/gemma-4-12b-qat"
    api_key = "lm-studio"
    
    try:
        # Pre-warm connection
        success, msg = llm.prepare_local_llm(base_url, model, api_key)
        print(f"Pre-warm status: {success} ({msg})")
        
        # Run agent
        record = llm.llm_parse_tender_agentic(md_text, provider, api_key, base_url, model)
        
        print("\n=== Agent Parsing Result ===")
        print(json.dumps(record, indent=2, ensure_ascii=True))

        
    except Exception as e:
        print(f"\nError running agent: {e}")

if __name__ == "__main__":
    main()
