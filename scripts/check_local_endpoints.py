import os
import sys
import json
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
CORE = os.path.join(SRC, 'core')
for p in (CORE, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

import llm

def try_resources(base_url, resources, timeout=3):
    for r in resources:
        try:
            print(f"Trying resource: {r}")
            text, used = llm.try_local_endpoint(base_url, r, method='POST', body={"model":"google/gemma-4-12b-qat","input":"test"}, timeout=timeout)
            err = llm.parse_response_error(text)
            print(f" -> URL: {used}\n -> Error parse: {err}\n -> Body preview: {text[:200]}\n")
        except Exception as e:
            print(f" -> Failed: {e}")

def main():
    base = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:1234'
    emb_resources = [
        'v1/embeddings', 'api/embeddings', 'embeddings', 'api/v1/embeddings',
        'v1/embed', 'api/v1/embed', 'embed', 'api/embed'
    ]
    print('Checking embedding endpoints...')
    try_resources(base, emb_resources, timeout=3)

if __name__ == '__main__':
    main()
