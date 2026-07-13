"""
chat_tab.py
~~~~~~~~~~~
Interactive chat panel for communicating with Ruhil, the agentic AI assistant.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import re
import json
from config import (
    BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN,
    FB, FL, FT
)
import db
import llm

SYSTEM_PROMPT = (
    "You are Ruhil, a helpful, intelligent agentic AI assistant for the GeM Tender Tracker application. "
    "You help users analyze government tenders, understand compliance requirements, suggest categories, draft document templates, "
    "and answer questions about bids in their database. Be concise, professional, and friendly. Always refer to yourself as Ruhil."
)

class ChatTab(tk.Frame):
    """Chat panel interface to interact with Ruhil."""
    
    def __init__(self, parent, main_app=None):
        super().__init__(parent, bg=BG)
        self.main_app = main_app
        self.conversation_history = []
        
        self._setup_ui()
        self._update_status()

    def _setup_ui(self):
        # 1. Header panel
        header = tk.Frame(self, bg=PANEL, height=50)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        # Agent Name
        agent_label = tk.Label(
            header, text="✨ Ruhil - Agentic AI Assistant",
            font=("Segoe UI", 12, "bold"), bg=PANEL, fg=TEXT
        )
        agent_label.pack(side="left", padx=16, pady=10)
        
        # Connection status label
        self.status_var = tk.StringVar(value="Status: Checking...")
        self.status_lbl = tk.Label(
            header, textvariable=self.status_var,
            font=("Segoe UI", 10), bg=PANEL, fg=MUTED
        )
        self.status_lbl.pack(side="right", padx=16, pady=10)
        
        # 2. Main Chat Display
        chat_frame = tk.Frame(self, bg=BG)
        chat_frame.pack(fill="both", expand=True, padx=16, pady=10)
        
        # Scrollable Text Widget for chat history
        self.chat_display = tk.Text(
            chat_frame, bg=CARD, fg=TEXT, font=("Segoe UI", 10),
            wrap="word", borderwidth=0, highlightthickness=1,
            highlightbackground=PANEL, padx=10, pady=10
        )
        self.chat_display.pack(fill="both", expand=True, side="left")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(chat_frame, orient="vertical", command=self.chat_display.yview)
        scrollbar.pack(fill="y", side="right")
        self.chat_display.configure(yscrollcommand=scrollbar.set)
        
        # Disable typing directly into history
        self.chat_display.configure(state="disabled")
        
        # Custom Tags for styled text
        self.chat_display.tag_configure("user_header", font=("Segoe UI", 10, "bold"), foreground=ACCENT)
        self.chat_display.tag_configure("ai_header", font=("Segoe UI", 10, "bold"), foreground=ACCENT2)
        self.chat_display.tag_configure("thinking_header", font=("Segoe UI", 9, "italic"), foreground=MUTED)
        self.chat_display.tag_configure("thinking_body", font=("Segoe UI", 9, "italic"), foreground=TEXTSUB, spacing1=4, spacing3=4)
        self.chat_display.tag_configure("body", font=("Segoe UI", 10), foreground=TEXT, spacing1=4, spacing3=8)
        
        # 3. Input Panel
        input_panel = tk.Frame(self, bg=PANEL, height=80)
        input_panel.pack(fill="x", side="bottom", padx=16, pady=(0, 16))
        
        # Text input widget
        self.input_text = tk.Text(
            input_panel, bg=CARD, fg=TEXT, font=("Segoe UI", 10),
            borderwidth=0, highlightthickness=1, highlightbackground=BG,
            padx=8, pady=8, height=3
        )
        self.input_text.pack(fill="both", expand=True, side="left", padx=10, pady=10)
        self.input_text.bind("<Return>", self._on_enter_pressed)
        
        # Button frame
        btn_frame = tk.Frame(input_panel, bg=PANEL)
        btn_frame.pack(side="right", fill="y", padx=(0, 10))
        
        # Send Button
        send_btn = tk.Button(
            btn_frame, text="Send ➔", font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg=BG, activebackground=ACCENT2,
            activeforeground=BG, borderwidth=0, padx=15,
            command=self._send_message
        )
        send_btn.pack(side="top", fill="x", pady=(10, 5), expand=True)
        
        # Clear Button
        clear_btn = tk.Button(
            btn_frame, text="Clear Chat", font=("Segoe UI", 9),
            bg=CARD, fg=TEXT, activebackground=PANEL,
            activeforeground=TEXT, borderwidth=0, padx=15,
            command=self._clear_chat
        )
        clear_btn.pack(side="bottom", fill="x", pady=(0, 10), expand=True)
        
        # Initial greeting from Ruhil
        self._add_message("Ruhil", "Hello! I am Ruhil, your agentic AI helper. How can I help you analyze tenders, create compliance documents, or manage your GeM bids today?")

    def _update_status(self):
        settings = db.load_settings()
        provider = settings.get("llm_provider", "Disabled")
        base_url = settings.get("llm_base_url", "http://localhost:1234")
        
        if provider == "Disabled":
            self.status_var.set("Status: LLM Provider Disabled")
            self.status_lbl.configure(fg=WARN)
        elif provider in ["LM Studio", "Ollama"]:
            # Check local server reachability in a background thread
            def check():
                reachable = llm.is_server_reachable(base_url)
                if reachable:
                    self.status_var.set(f"Status: {provider} Connected")
                    self.status_lbl.configure(fg=SUCCESS)
                else:
                    self.status_var.set(f"Status: {provider} Offline")
                    self.status_lbl.configure(fg=ERR)
            threading.Thread(target=check, daemon=True).start()
        else:
            self.status_var.set(f"Status: {provider} Active")
            self.status_lbl.configure(fg=SUCCESS)

    def _on_enter_pressed(self, event):
        # Prevent insertion of newline on Shift+Return, but execute on Return
        if not event.state & 0x1:  # No Shift modifier
            self._send_message()
            return "break"
        return None

    def _clear_chat(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.configure(state="disabled")
        self.conversation_history = []
        self._add_message("Ruhil", "Hello! Chat history cleared. How can I help you?")

    def _add_message(self, sender: str, text: str):
        self.chat_display.configure(state="normal")
        
        # Insert header
        if sender == "Ruhil":
            self.chat_display.insert(tk.END, "Ruhil\n", "ai_header")
        else:
            self.chat_display.insert(tk.END, f"{sender}\n", "user_header")
            
        # Extract and display thinking block if present
        thinking = llm.extract_thinking_block(text)
        if thinking:
            self.chat_display.insert(tk.END, "💭 Thought process:\n", "thinking_header")
            self.chat_display.insert(tk.END, f"{thinking}\n\n", "thinking_body")
            # Remove thinking tags from body output
            text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
            
        # Insert body text
        self.chat_display.insert(tk.END, f"{text}\n\n", "body")
        
        self.chat_display.configure(state="disabled")
        self.chat_display.see(tk.END)

    def _inject_db_context(self, message: str) -> str:
        # Search for bid numbers in message
        bid_pattern = r'\bGEM/\d{4}/[AB]/\d+\b'
        bids = re.findall(bid_pattern, message, re.IGNORECASE)
        context = ""
        
        if bids:
            tenders = db.load_all_tenders()
            for bid in bids:
                tender = next((t for t in tenders if t.get("bid_no", "").lower() == bid.lower()), None)
                if tender:
                    context += f"\n[Context for Tender Bid: {tender.get('bid_no')}]\n"
                    context += f"- Ministry/Dept: {tender.get('ministry', 'N/A')} / {tender.get('dept', 'N/A')}\n"
                    context += f"- Items/Category: {tender.get('items', 'N/A')} / {tender.get('category', 'N/A')}\n"
                    context += f"- Value: {tender.get('est_value', 'N/A')}\n"
                    context += f"- End Date: {tender.get('end_date', 'N/A')}\n"
                    context += f"- Status: {tender.get('status', 'N/A')}\n"
                    
        return context

    def _send_message(self):
        user_text = self.input_text.get("1.0", "end-1c").strip()
        if not user_text:
            return
            
        # Clear input field
        self.input_text.delete("1.0", tk.END)
        
        # Display user message
        self._add_message("You", user_text)
        
        # Load settings to verify LLM is configured
        settings = db.load_settings()
        provider = settings.get("llm_provider", "Disabled")
        if provider == "Disabled":
            self._add_message("Ruhil", "⚠️ No LLM Provider is configured. Please navigate to the Settings tab to set up a provider (Gemini, LM Studio, or Ollama).")
            return
            
        # Run AI query in a background thread to prevent GUI freezing
        def run_query():
            self._update_status()
            
            # Setup context and messages
            db_context = self._inject_db_context(user_text)
            
            # Construct a complete prompt
            full_prompt = f"{SYSTEM_PROMPT}\n"
            if db_context:
                full_prompt += f"Use this database context to help answer the query:\n{db_context}\n"
                
            full_prompt += f"User query: {user_text}\n"
            
            try:
                response = llm.call_llm(
                    prompt=full_prompt,
                    provider=provider,
                    api_key=settings.get("llm_api_key", ""),
                    base_url=settings.get("llm_base_url", "http://localhost:1234"),
                    model=settings.get("llm_model", "")
                )
                
                # Update UI in main thread
                self.after(0, lambda: self._add_message("Ruhil", response))
            except Exception as e:
                self.after(0, lambda: self._add_message("Ruhil", f"❌ Error querying AI agent: {e}"))
                
        threading.Thread(target=run_query, daemon=True).start()
