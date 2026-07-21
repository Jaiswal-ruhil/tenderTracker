"""
chat_tab.py
~~~~~~~~~~~
Interactive chat panel for communicating with Ruhil, the agentic AI assistant.
Features modern message bubbles, quick prompt chips, live LLM server status,
and database context injection.
"""

import os
import re
import json
import threading
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from config import (
    BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN,
    FB, FL, FT
)
import db
import llm

SYSTEM_PROMPT = (
    "You are Ruhil, a helpful, intelligent agentic AI assistant for the GeM Tender Tracker application. "
    "You help users analyze government tenders, understand compliance requirements, suggest categories, draft document templates, "
    "and answer questions about bids in their database. Be concise, professional, and friendly. Always refer to yourself as Ruhil. "
    "If the user asks to see your thinking process, what you are doing, or how you arrive at an answer, you MUST start your response "
    "by explaining your step-by-step reasoning inside a `<think>` block."
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
        # 1. Header Panel
        header = tk.Frame(self, bg=PANEL, height=52, highlightthickness=1, highlightbackground="#30363D")
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        title_fr = tk.Frame(header, bg=PANEL)
        title_fr.pack(side="left", padx=16, pady=8)

        tk.Label(
            title_fr, text="✨ Ruhil AI Assistant",
            font=("Segoe UI", 12, "bold"), bg=PANEL, fg=TEXT
        ).pack(side="left")

        # Active Model Tag
        self.model_badge = tk.Label(
            title_fr, text=" Gemma 4 ",
            font=("Segoe UI", 8, "bold"), bg="#1C3557", fg="#79C0FF", padx=4, pady=1
        )
        self.model_badge.pack(side="left", padx=(8, 0))
        
        # Connection status label & dot indicator
        self.status_var = tk.StringVar(value="Checking connection...")
        
        status_fr = tk.Frame(header, bg=PANEL)
        status_fr.pack(side="right", padx=16, pady=8)

        self.status_dot = tk.Label(status_fr, text="●", font=("Segoe UI", 10), bg=PANEL, fg=WARN)
        self.status_dot.pack(side="left", padx=(0, 4))

        self.status_lbl = tk.Label(
            status_fr, textvariable=self.status_var,
            font=("Segoe UI", 9, "bold"), bg=PANEL, fg=TEXTSUB
        )
        self.status_lbl.pack(side="left")
        
        # 2. Main Chat Display
        chat_frame = tk.Frame(self, bg=BG)
        chat_frame.pack(fill="both", expand=True, padx=16, pady=8)
        
        self.chat_display = tk.Text(
            chat_frame, bg=CARD, fg=TEXT, font=("Segoe UI", 10),
            wrap="word", borderwidth=0, highlightthickness=1,
            highlightbackground="#30363D", padx=14, pady=12
        )
        self.chat_display.pack(fill="both", expand=True, side="left")
        
        scrollbar = ttk.Scrollbar(chat_frame, orient="vertical", command=self.chat_display.yview)
        scrollbar.pack(fill="y", side="right")
        self.chat_display.configure(yscrollcommand=scrollbar.set)
        
        self.chat_display.configure(state="disabled")
        
        # Custom Tags for styled text & bubbles
        self.chat_display.tag_configure("user_header", font=("Segoe UI", 10, "bold"), foreground=ACCENT2, spacing1=10)
        self.chat_display.tag_configure("ai_header", font=("Segoe UI", 10, "bold"), foreground="#56D364", spacing1=10)
        self.chat_display.tag_configure("thinking_header", font=("Segoe UI", 9, "italic"), foreground=MUTED)
        self.chat_display.tag_configure("thinking_body", font=("Segoe UI", 9, "italic"), foreground=TEXTSUB, spacing1=4, spacing3=4)
        self.chat_display.tag_configure("body", font=("Segoe UI", 10), foreground=TEXT, spacing1=4, spacing3=8)

        # 3. Quick Prompt Chips
        chips_fr = tk.Frame(self, bg=BG)
        chips_fr.pack(fill="x", side="bottom", padx=16, pady=(0, 4))

        tk.Label(chips_fr, text="💡 Quick Questions:", font=("Segoe UI", 8, "bold"), bg=BG, fg=MUTED).pack(side="left", padx=(0, 6))

        prompts = [
            ("🎯 High-Value Tenders", "Show me high-value tenders in our database."),
            ("⏳ Closing in 48h", "Which tenders are closing in the next 48 hours?"),
            ("📁 Required Docs", "What compliance documents are required for filing?"),
            ("🏢 Matched Firms", "Which firms match our active tenders?"),
        ]

        for chip_lbl, prompt_text in prompts:
            def _chip_cmd(pt=prompt_text):
                self.input_text.delete("1.0", tk.END)
                self.input_text.insert("1.0", pt)
                self._send_message()

            btn = tk.Button(
                chips_fr, text=chip_lbl, command=_chip_cmd,
                bg=CARD, fg=TEXTSUB, activebackground=ACCENT2, activeforeground=TEXT,
                font=("Segoe UI", 8), relief="flat", padx=6, pady=2, cursor="hand2", bd=0
            )
            btn.pack(side="left", padx=(0, 4))

        # 4. Input Panel
        input_panel = tk.Frame(self, bg=PANEL, height=80, highlightthickness=1, highlightbackground="#30363D")
        input_panel.pack(fill="x", side="bottom", padx=16, pady=(0, 8))
        
        self.input_text = tk.Text(
            input_panel, bg=CARD, fg=TEXT, font=("Segoe UI", 10),
            borderwidth=0, highlightthickness=1, highlightbackground=BG,
            highlightcolor=ACCENT2, padx=10, pady=8, height=3
        )
        self.input_text.pack(fill="both", expand=True, side="left", padx=10, pady=10)
        self.input_text.bind("<Return>", self._on_enter_pressed)
        
        btn_frame = tk.Frame(input_panel, bg=PANEL)
        btn_frame.pack(side="right", fill="y", padx=(0, 10))
        
        send_btn = tk.Button(
            btn_frame, text="Send ➔", font=("Segoe UI", 9, "bold"),
            bg=ACCENT, fg="#FFFFFF", activebackground=ACCENT2, activeforeground="#FFFFFF",
            borderwidth=0, padx=16, cursor="hand2", command=self._send_message
        )
        send_btn.pack(side="top", fill="x", pady=(10, 4), expand=True)
        
        clear_btn = tk.Button(
            btn_frame, text="Clear", font=("Segoe UI", 8),
            bg=CARD, fg=TEXTSUB, activebackground=PANEL, activeforeground=TEXT,
            borderwidth=0, padx=16, cursor="hand2", command=self._clear_chat
        )
        clear_btn.pack(side="bottom", fill="x", pady=(0, 10), expand=True)
        
        # Initial greeting from Ruhil
        self._add_message("Ruhil", "Hello! I am Ruhil, your agentic AI helper. How can I help you analyze tenders, check compliance requirements, or manage your GeM bids today?")

    def _safe_set_status(self, text, color):
        try:
            if self.winfo_exists():
                self.status_var.set(text)
                self.status_lbl.configure(fg=color)
                self.status_dot.configure(fg=color)
        except Exception:
            pass

    def _update_status(self):
        settings = db.load_settings()
        provider = settings.get("llm_provider", "Local LLM (LM Studio / Ollama)")
        base_url = settings.get("llm_base_url", "http://localhost:1234/v1")
        model_name = settings.get("llm_model", "google/gemma-4-12b-qat")

        if model_name:
            short_model = os.path.basename(model_name)
            self.model_badge.configure(text=f" {short_model} ")

        if provider == "Disabled":
            self._safe_set_status("LLM Disabled", WARN)
        else:
            def check():
                reachable = llm.is_server_reachable(base_url)
                try:
                    if reachable:
                        self.after(0, lambda: self._safe_set_status(f"Connected ({provider})", SUCCESS))
                    else:
                        self.after(0, lambda: self._safe_set_status(f"Offline ({base_url})", ERR))
                except Exception:
                    pass
            threading.Thread(target=check, daemon=True).start()

    def _on_enter_pressed(self, event):
        if not event.state & 0x1:
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
        now_str = datetime.datetime.now().strftime("%H:%M")
        
        if sender == "Ruhil":
            self.chat_display.insert(tk.END, f"✨ Ruhil AI  ({now_str})\n", "ai_header")
        else:
            self.chat_display.insert(tk.END, f"👤 You  ({now_str})\n", "user_header")
            
        thinking = llm.extract_thinking_block(text)
        if thinking:
            self.chat_display.insert(tk.END, "💭 Thought process:\n", "thinking_header")
            self.chat_display.insert(tk.END, f"{thinking}\n\n", "thinking_body")
            text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
            
        self.chat_display.insert(tk.END, f"{text}\n\n", "body")
        
        self.chat_display.configure(state="disabled")
        self.chat_display.see(tk.END)

    def _inject_db_context(self, message: str) -> str:
        bid_pattern = r'\bGEM/\d{4}/[AB]/\d+\b'
        bids = re.findall(bid_pattern, message, re.IGNORECASE)
        context = ""
        
        if bids:
            tenders = db.load_all_tenders()
            for bid in bids:
                tender = next((t for t in tenders if t.get("bid_no", "").lower() == bid.lower()), None)
                if tender:
                    context += f"\n[Context for Tender: {tender.get('bid_no')}]\n"
                    context += f"- Ministry/Dept: {tender.get('ministry', 'N/A')} / {tender.get('dept', 'N/A')}\n"
                    context += f"- Category: {tender.get('category', 'N/A')} | Items: {tender.get('items', 'N/A')}\n"
                    context += f"- Value: {tender.get('est_value', 'N/A')}\n"
                    context += f"- End Date: {tender.get('end_date', 'N/A')}\n"
                    context += f"- Filing Status: {tender.get('filing_status', 'N/A')}\n"
                    
        return context

    def _send_message(self):
        user_text = self.input_text.get("1.0", "end-1c").strip()
        if not user_text:
            return
            
        self.input_text.delete("1.0", tk.END)
        self._add_message("You", user_text)
        
        settings = db.load_settings()
        provider = settings.get("llm_provider", "Local LLM (LM Studio / Ollama)")
        if provider == "Disabled":
            self._add_message("Ruhil", "⚠️ LLM Provider is disabled in Settings.")
            return
            
        def run_query():
            self._update_status()
            db_context = self._inject_db_context(user_text)
            
            full_prompt = f"{SYSTEM_PROMPT}\n"
            if db_context:
                full_prompt += f"Database Context:\n{db_context}\n"
            full_prompt += f"User Query: {user_text}\n"
            
            try:
                response = llm.call_llm(
                    prompt=full_prompt,
                    provider=provider,
                    api_key=settings.get("llm_api_key", ""),
                    base_url=settings.get("llm_base_url", "http://localhost:1234/v1"),
                    model=settings.get("llm_model", "google/gemma-4-12b-qat")
                )
                self.after(0, lambda: self._add_message("Ruhil", response))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: self._add_message("Ruhil", f"❌ Error querying AI agent: {err_msg}"))
                
        threading.Thread(target=run_query, daemon=True).start()
