# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

# Local imports
from config import BG, PANEL, CARD, ACCENT2, MUTED, TEXT, TEXTSUB, ERR, SUCCESS, WARN, FL

class LoadingDialog(tk.Toplevel):
    def __init__(self, parent, title="Please Wait", message="Processing...", task_fn=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()
        
        # Center the window relative to parent
        self.update_idletasks()
        w, h = 500, 420
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        
        # Disable close button
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Frame
        frame = tk.Frame(self, bg=PANEL, padx=15, pady=15, highlightthickness=1, highlightbackground="#30363D")
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        
        # Messages
        lbl_msg = tk.Label(frame, text=message, font=FL, bg=PANEL, fg=TEXT, wraplength=460, justify="center")
        lbl_msg.pack(pady=(5, 5))
        
        # Progress Bar
        self.progress = ttk.Progressbar(frame, orient="horizontal", length=440, mode="determinate", style="TProgressbar")
        self.progress.pack(pady=(5, 5))
        
        # Current Step Label
        self.lbl_step = tk.Label(frame, text="Initializing...", font=("Segoe UI", 9), bg=PANEL, fg=TEXTSUB, wraplength=460, justify="center")
        self.lbl_step.pack(pady=(2, 5))
        
        # Checklist Frame
        chk_frame = tk.Frame(frame, bg=BG, highlightthickness=1, highlightbackground="#30363D", padx=8, pady=8)
        chk_frame.pack(fill="both", expand=True, pady=(5, 5))
        
        self.chk_txt = tk.Text(chk_frame, bg=BG, fg=TEXT, font=("Consolas", 9), wrap="word", relief="flat", highlightthickness=0, height=8)
        self.chk_txt.pack(side="left", fill="both", expand=True)
        
        scroll = ttk.Scrollbar(chk_frame, orient="vertical", command=self.chk_txt.yview)
        scroll.pack(side="right", fill="y")
        self.chk_txt.configure(yscrollcommand=scroll.set)
        
        # Configure tags for colorful logging
        self.chk_txt.tag_config("ok", foreground=SUCCESS)
        self.chk_txt.tag_config("warn", foreground=WARN)
        self.chk_txt.tag_config("err", foreground=ERR)
        self.chk_txt.tag_config("info", foreground=TEXTSUB)
        self.chk_txt.configure(state="disabled")
        
        # Loading indicator dots
        self.dots_var = tk.StringVar(value="...")
        self.lbl_dots = tk.Label(frame, text="...", font=("Segoe UI", 12, "bold"), bg=PANEL, fg=ACCENT2)
        self.lbl_dots.pack(pady=(2, 2))
        
        self.task_fn = task_fn
        self.exception = None
        self.result = None
        
        self._animate_dots()
        
        if self.task_fn:
            import threading
            threading.Thread(target=self._run_task, daemon=True).start()
            
    def update_progress(self, percent, message=None):
        def _update():
            if self.winfo_exists():
                self.progress["value"] = percent
                if message:
                    self.lbl_step.configure(text=message)
                    self.append_checklist_item("info", message)
        self.after(0, _update)
            
    def append_checklist_item(self, level, message):
        def _append():
            if self.winfo_exists():
                self.chk_txt.configure(state="normal")
                icons = {
                    "ok": "✓ ",
                    "warn": "⚠ ",
                    "err": "✗ ",
                    "info": "ℹ "
                }
                icon = icons.get(level, "")
                # Skip duplicate messages if they are consecutive
                try:
                    last_line = self.chk_txt.get("end-2l", "end-1c")
                    if message in last_line:
                        self.chk_txt.configure(state="disabled")
                        return
                except Exception:
                    pass
                
                self.chk_txt.insert("end", f"{icon}{message}\n", level)
                self.chk_txt.see("end")
                self.chk_txt.configure(state="disabled")
        self.after(0, _append)
            
    def _animate_dots(self):
        if not self.winfo_exists():
            return
        curr = self.dots_var.get()
        if curr == "...":
            nxt = "."
        elif curr == ".":
            nxt = ".."
        elif curr == "..":
            nxt = "..."
        else:
            nxt = "."
        self.dots_var.set(nxt)
        self.lbl_dots.configure(text=nxt)
        self.after(400, self._animate_dots)
        
    def _run_task(self):
        try:
            import inspect
            if self.task_fn:
                sig = inspect.signature(self.task_fn)
                if len(sig.parameters) > 0:
                    self.result = self.task_fn(self.update_progress)
                else:
                    self.result = self.task_fn()
        except Exception as e:
            self.exception = e
        finally:
            if self.winfo_exists():
                self.after(0, self.destroy)
