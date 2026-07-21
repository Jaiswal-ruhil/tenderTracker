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
        
        # Center the window relative to parent with dynamic screen geometry
        self.update_idletasks()
        screen_w = parent.winfo_screenwidth() if hasattr(parent, 'winfo_screenwidth') else 1920
        screen_h = parent.winfo_screenheight() if hasattr(parent, 'winfo_screenheight') else 1080
        if steps:
            w = min(640, max(520, screen_w - 40))
            h = min(740, max(560, screen_h - 60))
        else:
            w = min(560, max(460, screen_w - 40))
            h = min(520, max(400, screen_h - 60))
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        self.minsize(500, 440)
        
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
            # 0. Visual Filing Pipeline Stage Bar
            self.pipeline_fr = tk.Frame(frame, bg=CARD, highlightthickness=1, highlightbackground="#30363D", padx=6, pady=6)
            self.pipeline_fr.pack(fill="x", pady=(2, 6))

            pipeline_stages = [
                ("1. Extract", "Specs"),
                ("2. Match", "Vault Docs"),
                ("3. Templates", "Declarations"),
                ("4. Verify", "Audit"),
                ("5. Portal", "Autofill")
            ]
            self.stage_badges = []
            for idx, (st_name, st_sub) in enumerate(pipeline_stages):
                badge_fr = tk.Frame(self.pipeline_fr, bg="#1C2128", highlightthickness=1, highlightbackground="#30363D", padx=4, pady=3)
                badge_fr.pack(side="left", fill="x", expand=True, padx=2)
                
                lbl_st = tk.Label(badge_fr, text=st_name, font=("Segoe UI", 8, "bold"), bg="#1C2128", fg=MUTED)
                lbl_st.pack()
                lbl_sub = tk.Label(badge_fr, text=st_sub, font=("Segoe UI", 7), bg="#1C2128", fg=TEXTSUB)
                lbl_sub.pack()

                self.stage_badges.append({
                    "frame": badge_fr,
                    "title": lbl_st,
                    "sub": lbl_sub,
                    "name": st_name
                })

            # 1. Logs console packed FIRST at bottom so it is never squished or hidden
            log_outer = tk.Frame(frame, bg=BG, highlightthickness=1, highlightbackground="#30363D", padx=6, pady=6)
            log_outer.pack(fill="x", side="bottom", pady=(6, 0))
            
            # Header frame with Step Filter & Copy button
            log_hdr_fr = tk.Frame(log_outer, bg=BG)
            log_hdr_fr.pack(fill="x", pady=(0, 2))
            
            tk.Label(log_hdr_fr, text="Detailed Logs", font=("Segoe UI", 8, "bold"), bg=BG, fg=TEXTSUB).pack(side="left")

            # Step filter dropdown
            self.step_filter_var = tk.StringVar(value="All Steps")
            step_options = ["All Steps"] + [f"Step {i+1}: {s[:25]}..." if len(s)>25 else f"Step {i+1}: {s}" for i, s in enumerate(steps)]
            step_combo = ttk.Combobox(log_hdr_fr, textvariable=self.step_filter_var, values=step_options, font=("Segoe UI", 7), width=22, state="readonly")
            step_combo.pack(side="left", padx=(10, 0))

            def _on_step_filter_change(e=None):
                self._refresh_log_console()

            step_combo.bind("<<ComboboxSelected>>", _on_step_filter_change)
            
            def copy_logs():
                logs_text = self._get_filtered_logs_text()
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
            
            self.chk_txt = tk.Text(log_outer, bg=BG, fg=TEXT, font=("Consolas", 8), wrap="word", relief="flat", highlightthickness=0, height=5)
            self.chk_txt.pack(side="left", fill="both", expand=True)
            
            scroll = ttk.Scrollbar(log_outer, orient="vertical", command=self.chk_txt.yview)
            scroll.pack(side="right", fill="y")
            self.chk_txt.configure(yscrollcommand=scroll.set)

            # 2. Checklist Frame packed SECOND in middle area with scrollable canvas
            chk_list_outer = tk.Frame(frame, bg=BG, highlightthickness=1, highlightbackground="#30363D", padx=10, pady=10)
            chk_list_outer.pack(fill="both", expand=True, pady=(5, 5))
            
            # Label
            tk.Label(chk_list_outer, text="Filing Pipeline Progress Steps", font=("Segoe UI", 9, "bold"), bg=BG, fg=TEXTSUB).pack(anchor="w", pady=(0, 5))
            
            chk_canvas = tk.Canvas(chk_list_outer, bg=BG, highlightthickness=0)
            chk_scroll = ttk.Scrollbar(chk_list_outer, orient="vertical", command=chk_canvas.yview)
            chk_canvas.configure(yscrollcommand=chk_scroll.set)

            self.chk_list_frame = tk.Frame(chk_canvas, bg=BG)
            _chk_win = chk_canvas.create_window((0, 0), window=self.chk_list_frame, anchor="nw")

            def _on_chk_configure(e):
                chk_canvas.configure(scrollregion=chk_canvas.bbox("all"))
            def _on_chk_canvas_configure(e):
                chk_canvas.itemconfig(_chk_win, width=e.width)

            self.chk_list_frame.bind("<Configure>", _on_chk_configure)
            chk_canvas.bind("<Configure>", _on_chk_canvas_configure)

            chk_canvas.pack(side="left", fill="both", expand=True)
            chk_scroll.pack(side="right", fill="y")

            def _bind_chk_mw(w):
                w.bind("<MouseWheel>", lambda e: chk_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
                for ch in w.winfo_children():
                    _bind_chk_mw(ch)
            self.chk_list_frame.bind("<Map>", lambda e: _bind_chk_mw(self.chk_list_frame))
            
            self.step_rows = []
            self.step_log_buffers = {}
            import time

            for i, step_name in enumerate(steps):
                self.step_log_buffers[i] = []
                row_fr = tk.Frame(self.chk_list_frame, bg=BG)
                row_fr.pack(fill="x", pady=2)
                
                # Check indicator icon
                lbl_icon = tk.Label(row_fr, text="  ○  ", font=("Segoe UI", 9), bg=BG, fg=MUTED, width=4)
                lbl_icon.pack(side="left")
                
                # Step name
                lbl_text = tk.Label(row_fr, text=step_name, font=("Segoe UI", 9), bg=BG, fg=TEXTSUB, anchor="w", wraplength=320, justify="left")
                lbl_text.pack(side="left", fill="x", expand=True)

                # Timer label
                lbl_timer = tk.Label(row_fr, text="", font=("Segoe UI", 8, "bold"), bg=BG, fg=MUTED, width=8, anchor="e")
                lbl_timer.pack(side="right", padx=(4, 2))

                # Copy Step Log button
                def _make_cp_step(idx=i, sname=step_name):
                    def _cp():
                        txt = self.get_step_logs_text(idx)
                        self.clipboard_clear()
                        self.clipboard_append(txt)
                        btn_cp.configure(text="Copied!")
                        self.after(1500, lambda: btn_cp.configure(text="📋 Log"))
                    return _cp

                btn_cp = tk.Button(row_fr, text="📋 Log", command=_make_cp_step(), font=("Segoe UI", 7), bg=CARD, fg=TEXTSUB, relief="flat", padx=3, pady=1)
                btn_cp.pack(side="right", padx=2)

                self.step_rows.append({
                    "icon": lbl_icon,
                    "text": lbl_text,
                    "timer": lbl_timer,
                    "copy_btn": btn_cp,
                    "original_text": step_name,
                    "status": "pending",
                    "start_time": None,
                    "end_time": None,
                    "elapsed_seconds": 0.0,
                    "reason": None
                })
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
            
            # Update visual pipeline stage badges if present
            if hasattr(self, "stage_badges") and self.stage_badges:
                num_badges = len(self.stage_badges)
                stage_idx = min(int((percent / 100.0) * num_badges), num_badges - 1) if percent < 100 else num_badges - 1
                for b_i, b_item in enumerate(self.stage_badges):
                    if percent >= 100 or b_i < stage_idx:
                        b_item["frame"].configure(bg="#1E3A2B", highlightbackground="#2EA043")
                        b_item["title"].configure(bg="#1E3A2B", fg="#3FB950")
                        b_item["sub"].configure(bg="#1E3A2B", fg="#A3E635")
                    elif b_i == stage_idx:
                        b_item["frame"].configure(bg="#1C3557", highlightbackground="#79C0FF")
                        b_item["title"].configure(bg="#1C3557", fg="#79C0FF")
                        b_item["sub"].configure(bg="#1C3557", fg="#58A6FF")
                    else:
                        b_item["frame"].configure(bg="#1C2128", highlightbackground="#30363D")
                        b_item["title"].configure(bg="#1C2128", fg="#484F58")
                        b_item["sub"].configure(bg="#1C2128", fg="#30363D")

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
        
        active_idx = getattr(self, "current_active_idx", 0)

        # Buffer log for current active step
        if hasattr(self, "step_log_buffers") and active_idx in self.step_log_buffers:
            self.step_log_buffers[active_idx].append((level, message))

        icons = {
            "ok": "✓ ",
            "warn": "⚠ ",
            "err": "✗ ",
            "info": "ℹ "
        }
        icon = icons.get(level, "")

        self._append_text_line(f"{icon}{message}", level)

        # Also update corresponding row UI if we got warning, error or running details
        if hasattr(self, "step_rows") and self.step_rows:
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

    def _append_text_line(self, line_str, level="info"):
        self.chk_txt.configure(state="normal")
        try:
            last_line = self.chk_txt.get("end-2l", "end-1c")
            if line_str in last_line:
                self.chk_txt.configure(state="disabled")
                return
        except Exception:
            pass
        self.chk_txt.insert("end", f"{line_str}\n", level)
        self.chk_txt.see("end")
        self.chk_txt.configure(state="disabled")

    def get_step_logs_text(self, step_idx=None) -> str:
        """Get formatted step logs text for clipboard copying or saving."""
        if not hasattr(self, "step_rows") or not self.step_rows:
            return self.chk_txt.get("1.0", "end-1c")

        icons = {"ok": "✓ ", "warn": "⚠ ", "err": "✗ ", "info": "ℹ "}
        lines = []

        if step_idx is not None and 0 <= step_idx < len(self.step_rows):
            row = self.step_rows[step_idx]
            orig_title = row["original_text"]
            dur = row.get("elapsed_seconds", 0.0)
            status = row.get("status", "pending")
            lines.append(f"==================================================")
            lines.append(f"STEP {step_idx+1}: {orig_title}")
            lines.append(f"Status: {status.upper()} | Time Taken: {dur:.2f}s")
            lines.append(f"==================================================")
            entries = self.step_log_buffers.get(step_idx, [])
            if not entries:
                lines.append("(No detailed logs recorded for this step)")
            for lvl, msg in entries:
                lines.append(f"{icons.get(lvl, '')}{msg}")
        else:
            # All steps
            lines.append("==================================================")
            lines.append("TENDER FILING WORKFLOW - FULL STEP LOG SUMMARY")
            lines.append("==================================================")
            for idx, row in enumerate(self.step_rows):
                orig_title = row["original_text"]
                dur = row.get("elapsed_seconds", 0.0)
                status = row.get("status", "pending")
                lines.append(f"\n--- [Step {idx+1}: {orig_title}] (Status: {status.upper()} | Time: {dur:.2f}s) ---")
                entries = self.step_log_buffers.get(idx, [])
                if not entries:
                    lines.append("  (No step logs)")
                for lvl, msg in entries:
                    lines.append(f"  {icons.get(lvl, '')}{msg}")

        return "\n".join(lines)

    def _get_filtered_logs_text(self) -> str:
        sel = getattr(self, "step_filter_var", None)
        filter_val = sel.get() if sel else "All Steps"
        if filter_val == "All Steps" or not hasattr(self, "step_rows"):
            return self.chk_txt.get("1.0", "end-1c")
        
        # Match step index from combobox value (e.g., "Step 1: ...")
        m = re.match(r'Step\s+(\d+):', filter_val)
        if m:
            idx = int(m.group(1)) - 1
            return self.get_step_logs_text(idx)
        return self.chk_txt.get("1.0", "end-1c")

    def _refresh_log_console(self):
        txt = self._get_filtered_logs_text()
        self.chk_txt.configure(state="normal")
        self.chk_txt.delete("1.0", "end")
        for line in txt.splitlines():
            level = "info"
            if line.startswith("✓"): level = "ok"
            elif line.startswith("⚠"): level = "warn"
            elif line.startswith("✗"): level = "err"
            self.chk_txt.insert("end", f"{line}\n", level)
        self.chk_txt.see("end")
        self.chk_txt.configure(state="disabled")

    def _update_row_ui(self, idx):
        if not self.winfo_exists():
            return
        row = self.step_rows[idx]
        status = row["status"]
        orig_text = row["original_text"]
        reason = row.get("reason")
        
        import time
        now = time.time()

        if status == "running":
            if row.get("start_time") is None:
                row["start_time"] = now
            elapsed = now - row["start_time"]
            row["timer"].configure(text=f"⏱ {elapsed:.1f}s", fg=ACCENT2)
        elif status in ("ok", "warn", "err"):
            if row.get("start_time") is not None and row.get("end_time") is None:
                row["end_time"] = now
                row["elapsed_seconds"] = max(0.05, round(now - row["start_time"], 2))
            elapsed = row.get("elapsed_seconds", 0.0)
            fg_col = SUCCESS if status == "ok" else (WARN if status == "warn" else ERR)
            row["timer"].configure(text=f"⏱ {elapsed:.1f}s" if elapsed > 0 else "", fg=fg_col)
        else:
            row["timer"].configure(text="", fg=MUTED)

        # Clean reason string
        clean_reason = ""
        if reason:
            clean_reason = reason.replace("[ERR]", "").replace("[warn]", "").replace("Step 7:", "").strip()
            if len(clean_reason) > 60:
                clean_reason = clean_reason[:57] + "..."
        
        # Clean running sub-process details
        running_detail = row.get("running_detail")
        clean_detail = ""
        if running_detail:
            clean_detail = running_detail.strip()
            clean_detail = re.sub(r'^\[[A-Za-z0-9_]+\]\s*', '', clean_detail)
            clean_detail = re.sub(r'^(Step \d+:)?\s*', '', clean_detail).strip()
            if len(clean_detail) > 35:
                clean_detail = clean_detail[:32] + "..."
        
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

        # Update live running timer UI
        if hasattr(self, "step_rows") and hasattr(self, "current_active_idx"):
            if 0 <= self.current_active_idx < len(self.step_rows):
                self._update_row_ui(self.current_active_idx)

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
