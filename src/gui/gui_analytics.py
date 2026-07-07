from datetime import datetime
import tkinter as tk
from tkinter import ttk

# Local imports
from config import BG, PANEL, CARD, MUTED, TEXT, SUCCESS, ERR, WARN, FL, FB, FT, ACCENT2
import db

class AnalyticsTabMixin:
    def _build_analytics_tab(self):
        container = tk.Frame(self.tab_analytics, bg=BG)
        container.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Grid layout for cards
        cards_fr = tk.Frame(container, bg=BG)
        cards_fr.pack(fill="x", pady=(0, 15))
        
        for col in range(4):
            cards_fr.columnconfigure(col, weight=1)
            
        def make_card(parent, col, title, color):
            card = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=15, pady=12)
            card.grid(row=0, column=col, padx=6, sticky="nsew")
            lbl_title = tk.Label(card, text=title, font=FL, bg=PANEL, fg=MUTED)
            lbl_title.pack(anchor="w")
            lbl_val = tk.Label(card, text="0", font=("Segoe UI", 24, "bold"), bg=PANEL, fg=color)
            lbl_val.pack(anchor="w", pady=(4, 0))
            
            # Hover glow animations
            def on_enter(e):
                card.configure(bg="#1C2128", highlightbackground=ACCENT2)
                lbl_title.configure(bg="#1C2128")
                lbl_val.configure(bg="#1C2128")
                
            def on_leave(e):
                card.configure(bg=PANEL, highlightbackground="#30363D")
                lbl_title.configure(bg=PANEL)
                lbl_val.configure(bg=PANEL)
                
            card.bind("<Enter>", on_enter)
            card.bind("<Leave>", on_leave)
            lbl_title.bind("<Enter>", on_enter)
            lbl_title.bind("<Leave>", on_leave)
            lbl_val.bind("<Enter>", on_enter)
            lbl_val.bind("<Leave>", on_leave)
            
            return lbl_val

        self.lbl_total_tenders = make_card(cards_fr, 0, "Total Tenders", TEXT)
        self.lbl_matching_wants = make_card(cards_fr, 1, "Matching Wants", SUCCESS)
        self.lbl_filtered_dont_wants = make_card(cards_fr, 2, "Filtered Don't Wants", ERR)
        self.lbl_not_filed = make_card(cards_fr, 3, "Not Filed Wants", WARN)
        
        # Bottom half
        bottom_fr = tk.Frame(container, bg=BG)
        bottom_fr.pack(fill="both", expand=True)
        
        bottom_fr.columnconfigure(0, weight=1)
        bottom_fr.columnconfigure(1, weight=1)
        bottom_fr.rowconfigure(0, weight=1)
        
        # Left Panel: Top Ministries Chart
        chart_fr = tk.Frame(bottom_fr, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=15, pady=12)
        chart_fr.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        tk.Label(chart_fr, text="Top Ministries / Departments", font=FT, bg=PANEL, fg=TEXT).pack(anchor="w", pady=(0, 10))
        
        self.chart_canvas = tk.Canvas(chart_fr, bg=PANEL, highlightthickness=0, height=260)
        self.chart_canvas.pack(fill="both", expand=True)
        
        # Bind Configure event to make the chart canvas responsive!
        self.chart_canvas.bind("<Configure>", lambda e: self._redraw_chart())
        
        # Right Panel: Upcoming Deadlines
        deadlines_fr = tk.Frame(bottom_fr, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=15, pady=12)
        deadlines_fr.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        tk.Label(deadlines_fr, text="Upcoming Deadlines (Wants)", font=FT, bg=PANEL, fg=TEXT).pack(anchor="w", pady=(0, 10))
        
        self.deadlines_scroll = ttk.Scrollbar(deadlines_fr, orient="vertical")
        self.deadlines_list = tk.Canvas(deadlines_fr, bg=PANEL, highlightthickness=0, yscrollcommand=self.deadlines_scroll.set)
        self.deadlines_scroll.configure(command=self.deadlines_list.yview)
        
        self.deadlines_inner_fr = tk.Frame(self.deadlines_list, bg=PANEL)
        self.deadlines_list.create_window((0, 0), window=self.deadlines_inner_fr, anchor="nw", tags="self.deadlines_inner_fr")
        
        # Guard against infinite configure loop
        self._updating_deadlines_scroll = False
        def on_inner_configure(e):
            if self._updating_deadlines_scroll:
                return
            self._updating_deadlines_scroll = True
            try:
                self.deadlines_list.configure(scrollregion=self.deadlines_list.bbox("all"))
            finally:
                self._updating_deadlines_scroll = False

        self._configuring_deadlines_canvas = False
        def on_canvas_configure(e):
            if self._configuring_deadlines_canvas:
                return
            self._configuring_deadlines_canvas = True
            try:
                self.deadlines_list.itemconfig("self.deadlines_inner_fr", width=e.width)
            finally:
                self._configuring_deadlines_canvas = False

        self.deadlines_inner_fr.bind("<Configure>", on_inner_configure)
        self.deadlines_list.bind("<Configure>", on_canvas_configure)
        
        self.deadlines_scroll.pack(side="right", fill="y")
        self.deadlines_list.pack(side="left", fill="both", expand=True)

        self._last_ministry_data = []

    def _update_analytics(self):
        total = len(self._records)
        wants = 0
        dont_wants = 0
        not_filed = 0
        
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
        
        ministry_counts = {}
        upcoming_deadlines = []
        
        for r in self._records:
            is_want = self._get_tender_status(r, inc_kws, exc_kws)
            if is_want:
                wants += 1
                if r.get("filing_status", "Not Filed") == "Not Filed":
                    not_filed += 1
                
                end_str = r.get("end_date", "")
                if end_str:
                    dt = self._parse_date_str(end_str)
                    if dt and dt >= datetime.now().date():
                        upcoming_deadlines.append((dt, end_str, r))
            else:
                dont_wants += 1
                
            min_name = r.get("ministry", "").strip() or "Unknown Ministry"
            ministry_counts[min_name] = ministry_counts.get(min_name, 0) + 1
            
        self.lbl_total_tenders.configure(text=str(total))
        self.lbl_matching_wants.configure(text=str(wants))
        self.lbl_filtered_dont_wants.configure(text=str(dont_wants))
        self.lbl_not_filed.configure(text=str(not_filed))
        
        # Save last ministry count sorted list for redrawing on configure
        self._last_ministry_data = sorted(ministry_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        self._redraw_chart()

        # Update deadlines
        for child in self.deadlines_inner_fr.winfo_children():
            child.destroy()
            
        upcoming_deadlines.sort(key=lambda x: x[0])
        display_deadlines = upcoming_deadlines[:10]
        
        if not display_deadlines:
            lbl = tk.Label(self.deadlines_inner_fr, text="No upcoming want deadlines.", font=FL, bg=PANEL, fg=MUTED)
            lbl.pack(pady=30)
        else:
            for dt, end_str, r in display_deadlines:
                row = tk.Frame(self.deadlines_inner_fr, bg=PANEL, pady=8)
                row.pack(fill="x", padx=10)
                
                days_left = (dt - datetime.now().date()).days
                if days_left == 0:
                    status_lbl = "TODAY"
                    status_color = ERR
                    status_bg = "#2A1D1D"
                elif days_left == 1:
                    status_lbl = "1 DAY LEFT"
                    status_color = ERR
                    status_bg = "#2A1D1D"
                else:
                    status_lbl = f"{days_left} DAYS LEFT"
                    status_color = WARN if days_left < 4 else SUCCESS
                    status_bg = "#2D261A" if days_left < 4 else "#1E2D1E"
                    
                lbl_left = tk.Label(row, text=r.get("bid_no", ""), font=FB, bg=PANEL, fg=TEXT, width=18, anchor="w", cursor="hand2")
                lbl_left.pack(side="left")
                
                lbl_mid = tk.Label(row, text=r.get("items", "")[:25], font=FL, bg=PANEL, fg=MUTED, anchor="w", cursor="hand2")
                lbl_mid.pack(side="left", fill="x", expand=True, padx=10)
                
                # Modern styled status badge
                badge = tk.Label(row, text=status_lbl, font=("Segoe UI", 8, "bold"), bg=status_bg, fg=status_color, padx=6, pady=2)
                badge.pack(side="right")
                
                # Hover highlights & click handling
                bid_no = r.get("bid_no", "")
                def make_hover_enter(target_row=row, left_lbl=lbl_left, mid_lbl=lbl_mid):
                    return lambda e: [
                        target_row.configure(bg="#21262D"),
                        left_lbl.configure(bg="#21262D"),
                        mid_lbl.configure(bg="#21262D")
                    ]
                def make_hover_leave(target_row=row, left_lbl=lbl_left, mid_lbl=lbl_mid):
                    return lambda e: [
                        target_row.configure(bg=PANEL),
                        left_lbl.configure(bg=PANEL),
                        mid_lbl.configure(bg=PANEL)
                    ]
                def make_click(b_no=bid_no):
                    return lambda e: self._locate_in_table(b_no)

                row.configure(cursor="hand2")
                row.bind("<Enter>", make_hover_enter())
                row.bind("<Leave>", make_hover_leave())
                row.bind("<Button-1>", make_click())
                
                lbl_left.bind("<Enter>", make_hover_enter())
                lbl_left.bind("<Leave>", make_hover_leave())
                lbl_left.bind("<Button-1>", make_click())
                
                lbl_mid.bind("<Enter>", make_hover_enter())
                lbl_mid.bind("<Leave>", make_hover_leave())
                lbl_mid.bind("<Button-1>", make_click())

                sep = tk.Frame(self.deadlines_inner_fr, bg="#30363D", height=1)
                sep.pack(fill="x", padx=10)

    def _redraw_chart(self):
        self.chart_canvas.delete("all")
        if not self._last_ministry_data:
            self.chart_canvas.create_text(150, 100, text="No ministry data available", fill=MUTED, font=FL)
            return

        max_count = self._last_ministry_data[0][1]
        canvas_w = self.chart_canvas.winfo_width()
        # If canvas is not yet initialized or zero size, default to 320
        if canvas_w < 50:
            canvas_w = 320
            
        bar_max_w = max(100, canvas_w - 220)
        
        # Draw background grid lines and labels
        for ratio in [0.25, 0.5, 0.75, 1.0]:
            grid_x = 130 + int(ratio * bar_max_w)
            grid_val = int(ratio * max_count)
            # Draw vertical grid line
            self.chart_canvas.create_line(grid_x, 15, grid_x, 240, fill="#21262D", dash=(3, 3))
            # Label at bottom
            self.chart_canvas.create_text(grid_x, 248, text=str(grid_val), fill=MUTED, font=("Segoe UI", 8))
            
        for idx, (min_name, count) in enumerate(self._last_ministry_data):
            y_offset = idx * 46 + 32
            disp_name = min_name[:18] + "..." if len(min_name) > 18 else min_name
            
            # Draw label
            self.chart_canvas.create_text(10, y_offset, text=disp_name, fill=TEXT, font=FL, anchor="w")
            
            bar_w = int((count / max_count) * bar_max_w)
            bar_w = max(4, bar_w)
            
            # Color coding: top gets bright blue, others get standard accent blue
            bar_color = "#388BFD" if idx == 0 else "#1F6FEB"
            
            group_tag = f"bar_group_{idx}"
            bar_tag = f"bar_line_{idx}"
            
            # Draw label
            self.chart_canvas.create_text(10, y_offset, text=disp_name, fill=TEXT, font=FL, anchor="w", tags=(group_tag, f"text_{idx}"))
            
            # Draw drop shadow (offset by 2px down/right)
            self.chart_canvas.create_line(132, y_offset + 2, 132 + bar_w, y_offset + 2, width=18, capstyle="round", fill="#090D13", tags=group_tag)
            
            # Draw rounded bar
            self.chart_canvas.create_line(130, y_offset, 130 + bar_w, y_offset, width=18, capstyle="round", fill=bar_color, tags=(group_tag, bar_tag))
            
            # Draw count label
            self.chart_canvas.create_text(130 + bar_w + 12, y_offset, text=str(count), fill=TEXT, font=FB, anchor="w", tags=(group_tag, f"count_{idx}"))

            # Interactive bindings for ministries
            def make_enter_handler(bt=bar_tag):
                return lambda e: [
                    self.chart_canvas.itemconfig(bt, fill="#58A6FF"),  # Bright blue glow
                    self.chart_canvas.configure(cursor="hand2")
                ]
            def make_leave_handler(bt=bar_tag, col=bar_color):
                return lambda e: [
                    self.chart_canvas.itemconfig(bt, fill=col),
                    self.chart_canvas.configure(cursor="")
                ]
            def make_click_handler(name=min_name):
                return lambda e: self._filter_by_ministry(name)

            self.chart_canvas.tag_bind(group_tag, "<Enter>", make_enter_handler())
            self.chart_canvas.tag_bind(group_tag, "<Leave>", make_leave_handler())
            self.chart_canvas.tag_bind(group_tag, "<Button-1>", make_click_handler())

    def _filter_by_ministry(self, name):
        self.notebook.select(self.tab_table)
        # Reset filters to ensure the search finds it
        if hasattr(self, "view_var"):
            self.view_var.set("All Tenders")
        if hasattr(self, "status_view_var"):
            self.status_view_var.set("All")
        if hasattr(self, "date_filter_preset_var"):
            self.date_filter_preset_var.set("All Dates")
            self._apply_date_filter_preset(initial=False)
            
        if hasattr(self, "search_var"):
            self.search_var.set(name)
            
        self._refresh_table_view()
        self._log("info", f"Filtered Table View to Ministry: '{name}'")
