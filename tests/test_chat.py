import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import tkinter as tk

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'core')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'gui')))

from components import chat_tab


class TestChatTab(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()  # Hide the root window

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        # Mock settings and LLM connections so the UI test doesn't do real requests
        self.mock_settings = {
            "llm_provider": "Disabled",
            "llm_base_url": "http://localhost:1234",
            "llm_model": "test-model"
        }
        
    @patch('components.chat_tab.db.load_settings')
    def test_init_and_greeting(self, mock_load):
        mock_load.return_value = self.mock_settings
        
        tab = chat_tab.ChatTab(self.root)
        
        # Verify greetings are inserted
        chat_text = tab.chat_display.get("1.0", tk.END)
        self.assertIn("Ruhil", chat_text)
        self.assertIn("your agentic AI helper", chat_text)
        tab.destroy()

    @patch('components.chat_tab.db.load_settings')
    def test_add_message(self, mock_load):
        mock_load.return_value = self.mock_settings
        tab = chat_tab.ChatTab(self.root)
        
        tab._add_message("You", "Test message content")
        
        chat_text = tab.chat_display.get("1.0", tk.END)
        self.assertIn("You", chat_text)
        self.assertIn("Test message content", chat_text)
        tab.destroy()

    @patch('components.chat_tab.db.load_settings')
    def test_thinking_block_extraction(self, mock_load):
        mock_load.return_value = self.mock_settings
        tab = chat_tab.ChatTab(self.root)
        
        raw_response = "<think>Calculating things</think>Here is the final answer."
        tab._add_message("Ruhil", raw_response)
        
        chat_text = tab.chat_display.get("1.0", tk.END)
        self.assertIn("Thought process:", chat_text)
        self.assertIn("Calculating things", chat_text)
        self.assertIn("Here is the final answer.", chat_text)
        self.assertNotIn("<think>", chat_text)
        tab.destroy()

    @patch('components.chat_tab.db.load_all_tenders')
    @patch('components.chat_tab.db.load_settings')
    def test_inject_db_context(self, mock_load, mock_load_tenders):
        mock_load.return_value = self.mock_settings
        mock_load_tenders.return_value = [{
            "bid_no": "GEM/2026/B/9520877",
            "ministry": "Ministry of Power",
            "dept": "NTPC",
            "category": "Cables"
        }]
        
        tab = chat_tab.ChatTab(self.root)
        
        # Check matching context
        context = tab._inject_db_context("Tell me about GEM/2026/B/9520877")
        self.assertIn("GEM/2026/B/9520877", context)
        self.assertIn("Ministry of Power", context)
        self.assertIn("Cables", context)
        
        # Check no matching context
        no_context = tab._inject_db_context("Some normal sentence")
        self.assertEqual(no_context, "")
        tab.destroy()
