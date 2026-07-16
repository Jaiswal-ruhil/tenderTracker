# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
import queue
import threading
import re

# Local imports
from config import BG, PANEL, CARD, ACCENT2, MUTED, TEXT, TEXTSUB, ERR, SUCCESS, WARN, FL

class LoadingDialog(tk.Toplevel):
    def __init__(self, parent, title="Please Wait", message="Processing...", task_fn=None, steps=None, on_done=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(True, True)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()
        
        # Center the window relative to parent
        self.update_idletasks()
        if steps:
            w, h = 580, 680
        else:
            w, h = 540, 480
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        
        # Disable close button
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Frame
        frame = tk.Frame(self, bg=PANEL, padx=15, pady=15, highlightthickness=1, highlightbackground="#30363D")
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        self.frame = frame
        
        # Messages
        lbl_msg = tk.Label(frame, text=message, font=FL, bg=PANEL, fg=TEXT, wraplength=460, justify="center")
        lbl_msg.pack(pady=(5, 5))
        
        # Progress Bar
        self.progress = ttk.Progressbar(frame, orient="horizontal", length=440, mode="determinate", style="TProgressbar")
        self.progress.pack(pady=(5, 5))
        
        # Current Step Label
        self.lbl_step = tk.Label(frame, text="Initializing...", font=("Segoe UI", 9), bg=PANEL, fg=TEXTSUB, wraplength=460, justify="center")
        self.lbl_step.pack(pady=(2, 5))
        
        if steps:
            # Checklist Frame
            chk_list_outer = tk.Frame(frame, bg=BG, highlightthickness=1, highlightbackground="#30363D", padx=10, pady=10)
            chk_list_outer.pack(fill="both", expand=True, pady=(5, 5))
            
            # Label
            tk.Label(chk_list_outer, text="Filing Progress Steps", font=("Segoe UI", 9, "bold"), bg=BG, fg=TEXTSUB).pack(anchor="w", pady=(0, 5))
            
            self.chk_list_frame = tk.Frame(chk_list_outer, bg=BG)
            self.chk_list_frame.pack(fill="both", expand=True)
            
            self.step_rows = []
            for i, step_name in enumerate(steps):
                row_fr = tk.Frame(self.chk_list_frame, bg=BG)
                row_fr.pack(fill="x", pady=2)
                
                # Check indicator icon
                lbl_icon = tk.Label(row_fr, text="  ○  ", font=("Segoe UI", 9), bg=BG, fg=MUTED, width=4)
                lbl_icon.pack(side="left")
                
                # Step name
                lbl_text = tk.Label(row_fr, text=step_name, font=("Segoe UI", 9), bg=BG, fg=TEXTSUB, anchor="w", wraplength=440, justify="left")
                lbl_text.pack(side="left", fill="x", expand=True)
                
                self.step_rows.append({
                    "icon": lbl_icon,
                    "text": lbl_text,
                    "original_text": step_name,
                    "status": "pending",
                    "reason": None
                })
            
            # Logs console at the bottom
            log_outer = tk.Frame(frame, bg=BG, highlightthickness=1, highlightbackground="#30363D", padx=6, pady=6)
            log_outer.pack(fill="x", side="bottom", pady=(5, 0))
            
            # Header frame with Copy button
            log_hdr_fr = tk.Frame(log_outer, bg=BG)
            log_hdr_fr.pack(fill="x", pady=(0, 2))
            
            tk.Label(log_hdr_fr, text="Detailed Logs", font=("Segoe UI", 8, "bold"), bg=BG, fg=TEXTSUB).pack(side="left")
            
            def copy_logs():
                logs_text = self.chk_txt.get("1.0", "end-1c")
                self.clipboard_clear()
                self.clipboard_append(logs_text)
                btn_copy.configure(text="Copied!")
                self.after(1500, lambda: btn_copy.configure(text="Copy Logs"))
                
            btn_copy = tk.Button(
                log_hdr_fr, 
                text="Copy Logs", 
                command=copy_logs, 
                font=("Segoe UI", 7, "bold"), 
                bg=CARD, 
                fg=TEXTSUB, 
                relief="flat", 
                activebackground=PANEL, 
                activeforeground=TEXT,
                padx=6,
                pady=1
            )
            btn_copy.pack(side="right")
            
            self.chk_txt = tk.Text(log_outer, bg=BG, fg=TEXT, font=("Consolas", 8), wrap="word", relief="flat", highlightthickness=0, height=4)
            self.chk_txt.pack(side="left", fill="both", expand=True)
            
            scroll = ttk.Scrollbar(log_outer, orient="vertical", command=self.chk_txt.yview)
            scroll.pack(side="right", fill="y")
            self.chk_txt.configure(yscrollcommand=scroll.set)
        else:
            # Classic view (just the big log console)
            chk_frame = tk.Frame(frame, bg=BG, highlightthickness=1, highlightbackground="#30363D", padx=8, pady=8)
            chk_frame.pack(fill="both", expand=True, pady=(5, 5))
            
            # Header frame with Copy button
            log_hdr_fr = tk.Frame(chk_frame, bg=BG)
            log_hdr_fr.pack(fill="x", pady=(0, 2))
            
            tk.Label(log_hdr_fr, text="Detailed Logs", font=("Segoe UI", 9, "bold"), bg=BG, fg=TEXTSUB).pack(side="left")
            
            def copy_logs_classic():
                logs_text = self.chk_txt.get("1.0", "end-1c")
                self.clipboard_clear()
                self.clipboard_append(logs_text)
                btn_copy_classic.configure(text="Copied!")
                self.after(1500, lambda: btn_copy_classic.configure(text="Copy Logs"))
                
            btn_copy_classic = tk.Button(
                log_hdr_fr, 
                text="Copy Logs", 
                command=copy_logs_classic, 
                font=("Segoe UI", 8, "bold"), 
                bg=CARD, 
                fg=TEXTSUB, 
                relief="flat", 
                activebackground=PANEL, 
                activeforeground=TEXT,
                padx=8,
                pady=2
            )
            btn_copy_classic.pack(side="right")
            
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
        self.result = None
        self.exception = None
        self.task_finished = False
        self.on_done = on_done  # optional callback(result, exception) called on main thread
        
        self.queue = queue.Queue()
        
        self.current_active_idx = 0
        if steps:
            self.step_rows[0]["status"] = "running"
            self._update_row_ui(0)
            
        self._animate_dots()
        self.after(50, self._check_queue)
        
        if self.task_fn:
            threading.Thread(target=self._run_task, daemon=True).start()
            
    def update_progress(self, percent, message=None):
        self.queue.put(("progress", percent, message))
        if threading.current_thread() is threading.main_thread():
            self._check_queue()
            
    def append_checklist_item(self, level, message):
        self.queue.put(("log", level, message))
        if threading.current_thread() is threading.main_thread():
            self._check_queue()
            
    def _check_queue(self):
        if not self.winfo_exists():
            return
        while True:
            try:
                item = self.queue.get_nowait()
                if item == "finished":
                    self._on_task_finished()
                    return
                elif isinstance(item, tuple):
                    if item[0] == "progress":
                        self._process_update_progress(item[1], item[2])
                    elif item[0] == "log":
                        self._process_append_checklist_item(item[1], item[2])
            except queue.Empty:
                break
        
        if self.winfo_exists() and not self.task_finished:
            self.after(50, self._check_queue)

    def _process_update_progress(self, percent, message=None):
        if not self.winfo_exists():
            return
        self.progress["value"] = percent
        if message:
            self.lbl_step.configure(text=message)
            self._process_append_checklist_item("info", message)
        
        # Update checklist statuses
        if hasattr(self, "step_rows") and self.step_rows:
            num_steps = len(self.step_rows)
            if num_steps == 11:
                thresholds = [10, 20, 35, 45, 60, 72, 80, 85, 92, 100]
                active_idx = 0
                for i, t in enumerate(thresholds):
                    if percent >= t:
                        active_idx = i + 1
            else:
                if percent >= 100:
                    active_idx = num_steps - 1
                else:
                    active_idx = min(int((percent / 100.0) * num_steps), num_steps - 1)
            
            self.current_active_idx = active_idx
            
            for i in range(num_steps):
                row = self.step_rows[i]
                if percent >= 100:
                    if row["status"] != "err":
                        row["status"] = "ok"
                        row["reason"] = None
                else:
                    if i < active_idx:
                        if row["status"] != "err":
                            row["status"] = "ok"
                            row["reason"] = None
                    elif i == active_idx:
                        if row["status"] not in ("warn", "err"):
                            row["status"] = "running"
                    else:
                        row["status"] = "pending"
                self._update_row_ui(i)

    def _process_append_checklist_item(self, level, message):
        if not self.winfo_exists():
            return
        self.chk_txt.configure(state="normal")
        icons = {
            "ok": "✓ ",
            "warn": "⚠ ",
            "err": "✗ ",
            "info": "ℹ "
        }
        icon = icons.get(level, "")
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
        
        # Also update corresponding row UI if we got warning, error or running details
        if hasattr(self, "step_rows") and self.step_rows:
            active_idx = getattr(self, "current_active_idx", 0)
            if 0 <= active_idx < len(self.step_rows):
                row = self.step_rows[active_idx]
                if level == "err":
                    row["status"] = "err"
                    row["reason"] = message
                    self._update_row_ui(active_idx)
                elif level == "warn" and row["status"] != "err":
                    row["status"] = "warn"
                    row["reason"] = message
                    self._update_row_ui(active_idx)
                elif level == "ok" and row["status"] == "warn":
                    row["status"] = "ok"
                    row["reason"] = None
                    self._update_row_ui(active_idx)
                elif level == "info" and row["status"] == "running":
                    row["running_detail"] = message
                    self._update_row_ui(active_idx)

    def _update_row_ui(self, idx):
        if not self.winfo_exists():
            return
        row = self.step_rows[idx]
        status = row["status"]
        orig_text = row["original_text"]
        reason = row.get("reason")
        
        # Clean reason string: strip prefix symbols/logs if needed, keep it simple
        clean_reason = ""
        if reason:
            clean_reason = reason.replace("[ERR]", "").replace("[warn]", "").replace("Step 7:", "").strip()
            # Truncate clean_reason if it is very long to prevent visual layout breaking
            if len(clean_reason) > 60:
                clean_reason = clean_reason[:57] + "..."
        
        # Clean running sub-process details
        running_detail = row.get("running_detail")
        clean_detail = ""
        if running_detail:
            clean_detail = running_detail.strip()
            clean_detail = re.sub(r'^\[[A-Za-z0-9_]+\]\s*', '', clean_detail)
            clean_detail = re.sub(r'^(Step \d+:)?\s*', '', clean_detail).strip()
            # Truncate if very long
            if len(clean_detail) > 40:
                clean_detail = clean_detail[:37] + "..."
        
        if status == "warn" and clean_reason:
            display_text = f"{orig_text} (Warning: {clean_reason})"
        elif status == "err" and clean_reason:
            display_text = f"{orig_text} (Error: {clean_reason})"
        elif status == "running" and clean_detail:
            display_text = f"{orig_text} ({clean_detail})"
        else:
            display_text = orig_text
            
        row["text"].configure(text=display_text)
        
        if status == "pending":
            row["icon"].configure(text="  ○  ", fg=MUTED)
            row["text"].configure(fg=TEXTSUB, font=("Segoe UI", 9))
        elif status == "running":
            row["icon"].configure(text="  ▶  ", fg=ACCENT2)
            row["text"].configure(fg=TEXT, font=("Segoe UI", 9, "bold"))
        elif status == "ok":
            row["icon"].configure(text="  ✓  ", fg=SUCCESS)
            row["text"].configure(fg=SUCCESS, font=("Segoe UI", 9))
        elif status == "warn":
            row["icon"].configure(text="  ⚠  ", fg=WARN)
            row["text"].configure(fg=WARN, font=("Segoe UI", 9))
        elif status == "err":
            row["icon"].configure(text="  ✗  ", fg=ERR)
            row["text"].configure(fg=ERR, font=("Segoe UI", 9, "bold"))
            
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
        
    def _handle_failure(self):
        if not self.winfo_exists():
            return
        self.lbl_dots.configure(text="Process Failed", fg=ERR)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        
        def _close_btn_cmd():
            result = self.result
            exc = self.exception
            self.destroy()
            if self.on_done:
                self.on_done(result, exc)
                
        btn_close = tk.Button(
            self.frame, 
            text="Close", 
            command=_close_btn_cmd, 
            bg=CARD, 
            fg=TEXT, 
            activebackground=PANEL, 
            activeforeground=TEXT, 
            font=("Segoe UI", 9, "bold"),
            relief="flat", 
            highlightthickness=1, 
            highlightbackground="#30363D", 
            padx=20, 
            pady=6
        )
        btn_close.pack(pady=(12, 0))
        
    def _on_task_finished(self, event=None):
        if self.exception:
            self._handle_failure()
        else:
            if self.winfo_exists():
                def _close_and_notify():
                    result = self.result
                    exc = self.exception
                    if self.winfo_exists():
                        self.destroy()
                    if self.on_done:
                        self.on_done(result, exc)
                self.after(1500, _close_and_notify)

    def _run_task(self):
        try:
            import inspect
            if self.task_fn:
                sig = inspect.signature(self.task_fn)
                if len(sig.parameters) > 0:
                    self.result = self.task_fn(self.update_progress)
                else:
                    self.result = self.task_fn()
            
            # Check if result was a failure dictionary
            if isinstance(self.result, dict) and not self.result.get('success', True):
                self.exception = ValueError(self.result.get('error', 'Process failed'))
        except Exception as e:
            self.exception = e
        finally:
            self.queue.put("finished")
            self.task_finished = True
