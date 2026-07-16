import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json

# Add src/core to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "core")))

import llm_agent

class TestLLMAgent(unittest.TestCase):

    @patch("llm_agent._post_json")
    def test_run_tender_agent_direct_final(self, mock_post):
        # Mock immediate final JSON response (no tool calling required)
        final_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "bid_no": "GEM/2026/B/9520877",
                        "items": "Electric Motor 11KW",
                        "est_value": "150000"
                    })
                }
            }]
        }
        mock_post.return_value = json.dumps(final_response)

        res = llm_agent.run_tender_agent(
            pdf_text="Some random PDF text",
            base_url="http://localhost:1234",
            model="google/gemma-4-12b-qat"
        )

        self.assertEqual(res.get("bid_no"), "GEM/2026/B/9520877")
        self.assertEqual(res.get("items"), "Electric Motor 11KW")
        self.assertEqual(res.get("est_value"), "150000")

    @patch("llm_agent._post_json")
    @patch("llm_agent.execute_tool")
    def test_run_tender_agent_with_tool_calling(self, mock_exec_tool, mock_post):
        # Mock step 1: LLM requests tool call
        step1_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "call_abc123",
                        "type": "function",
                        "function": {
                            "name": "extract_bid_metadata",
                            "arguments": "{\"pdf_text\": \"Sample PDF\"}"
                        }
                    }]
                }
            }]
        }
        # Mock step 2: LLM produces final response after seeing tool output
        step2_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "bid_no": "GEM/2026/B/9520877",
                        "items": "Slipring Motor"
                    })
                }
            }]
        }

        # Mock requests returning sequentially
        mock_post.side_effect = [
            json.dumps(step1_response),  # 1st loop call (probe)
            json.dumps(step1_response),  # 2nd call (iteration 1)
            json.dumps(step2_response)   # 3rd call (iteration 2)
        ]

        # Tool result mock
        mock_exec_tool.return_value = "{\"bid_no\": \"GEM/2026/B/9520877\"}"

        res = llm_agent.run_tender_agent(
            pdf_text="Sample PDF",
            base_url="http://localhost:1234",
            model="google/gemma-4-12b-qat"
        )

        self.assertEqual(res.get("bid_no"), "GEM/2026/B/9520877")
        self.assertEqual(res.get("items"), "Slipring Motor")
        self.assertTrue(mock_exec_tool.called)

    @patch("llm_agent._post_json")
    def test_find_chat_url_skips_unexpected_endpoint_body(self, mock_post):
        # First candidate (/v1/chat/completions) returns "Unexpected endpoint or method."
        # Second candidate (/api/v1/chat/completions) returns "Unexpected endpoint."
        # Third candidate (/chat/completions) succeeds with valid JSON
        mock_post.side_effect = [
            "Unexpected endpoint or method. (POST /v1/chat/completions)",
            "Unexpected endpoint. (POST /api/v1/chat/completions)",
            '{"choices": []}'
        ]
        url = llm_agent._find_chat_url("http://localhost:1234", {})
        self.assertEqual(url, "http://localhost:1234/chat/completions")

    @patch("llm._local_chat_request")
    def test_call_llm_token_limits(self, mock_local_chat):
        import llm
        
        # 1. Test document extraction prompt gets 2048 tokens
        llm.call_llm(
            prompt="Extract document requirements from this tender text...",
            provider="Local LLM (LM Studio / Ollama)",
            api_key="",
            base_url="http://localhost:1234",
            model="test-model"
        )
        mock_local_chat.assert_called_with(
            "Extract document requirements from this tender text...",
            "http://localhost:1234",
            "test-model",
            "",
            False,
            timeout=600,
            max_tokens=4096
        )
        
        # 2. Test category prompt gets 128 tokens
        llm.call_llm(
            prompt="Suggest keywords for item category...",
            provider="Local LLM (LM Studio / Ollama)",
            api_key="",
            base_url="http://localhost:1234",
            model="test-model"
        )
        mock_local_chat.assert_called_with(
            "Suggest keywords for item category...",
            "http://localhost:1234",
            "test-model",
            "",
            False,
            timeout=600,
            max_tokens=128
        )

if __name__ == '__main__':
    unittest.main()
