from unittest.mock import patch, MagicMock
import urllib.error
import sys
sys.path.insert(0, 'src/core')
import llm

def side_effect(req, timeout=10):
    url = req.full_url
    if url.endswith('/v1/embeddings'):
        raise urllib.error.HTTPError(url, 404, 'Not Found', hdrs=None, fp=None)
    mock_resp = MagicMock()
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.read.return_value = b'{"data": [{"embedding": [0.4, 0.5, 0.6]}]}'
    print('REQ.DATA:', req.data)
    return mock_resp

with patch('urllib.request.urlopen', side_effect=side_effect):
    try:
        emb = llm.get_embedding('test text', 'Local LLM (LM Studio / Ollama)', '', 'http://localhost:1234/v1', 'my-local-model')
        print('EMB:', emb)
    except Exception as e:
        import traceback
        traceback.print_exc()
