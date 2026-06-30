import os
import re
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import calendar
import webbrowser

# Local imports
from config import (
    BG, PANEL, CARD, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN,
    FL, FB, FT, TV_IDS
)

class CalendarTabMixin:
    def _build_calendar_tab(self):
        # We split the calendar tab into left (grid) and right (details sidebar)
        self.cal_pane = tk.PanedWindow(self.tab_calendar, orient="horizontal", bg=BG,
                                       sashwidth=4, sashrelief="flat", handlesize=0)
        self.cal_pane.pack(fill="both", expand=True, padx=4, pady=4)

        # LEFT PANEL: Calendar Grid Container
        left_fr = tk.Frame(self.cal_pane, bg=BG)
        self.cal_pane.add(left_fr, minsize=500, stretch="always")

        # Month Navigation Bar
        nav_fr = tk.Frame(left_fr, bg=PANEL, pady=6, padx=10,
                          highlightthickness=1, highlightbackground="#30363D")
        nav_fr.pack(fill="x", pady=(0, 6))

        self.cal_prev_btn = self._btn(nav_fr, " ◀ ", self._cal_prev_month, bg=CARD)
        self.cal_prev_btn.pack(side="left")

        self.cal_month_lbl = tk.Label(nav_fr, text="", font=FT, bg=PANEL, fg=TEXT)
        self.cal_month_lbl.pack(side="left", expand=True)

        self.cal_next_btn = self._btn(nav_fr, " ▶ ", self._cal_next_month, bg=CARD)
        self.cal_next_btn.pack(side="right")

        # Grid of Days (Mon to Sun headers + 6 weeks of cards)
        self.cal_grid_fr = tk.Frame(left_fr, bg=BG)
        self.cal_grid_fr.pack(fill="both", expand=True)

        # Weekdays headers
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for idx, day in enumerate(weekdays):
            self.cal_grid_fr.columnconfigure(idx, weight=1, uniform="daycol")
            lbl = tk.Label(self.cal_grid_fr, text=day[:3], font=("Segoe UI", 9, "bold"),
                           bg=BG, fg=MUTED, pady=4)
            lbl.grid(row=0, column=idx, sticky="ew")

        # 6 rows for weeks
        for r in range(1, 7):
            self.cal_grid_fr.rowconfigure(r, weight=1, uniform="weekrow")

        # RIGHT PANEL: Details Sidebar
        right_fr = tk.Frame(self.cal_pane, bg=PANEL, highlightthickness=1, highlightbackground="#30363D")
        self.cal_pane.add(right_fr, minsize=280, width=320, stretch="never")

        # Selected Date Label Header
        self.cal_sel_date_lbl = tk.Label(right_fr, text="", font=("Segoe UI", 10, "bold"),
                                         bg=PANEL, fg=ACCENT2, pady=8, wraplength=300)
        self.cal_sel_date_lbl.pack(fill="x", padx=10)

        # Divider line
        div = tk.Frame(right_fr, height=1, bg="#30363D")
        div.pack(fill="x", padx=10, pady=(0, 10))

        # Scrollable container for detail cards
        self.cal_scroll_canvas = tk.Canvas(right_fr, bg=PANEL, highlightthickness=0)
        self.cal_scroll_canvas.pack(side="left", fill="both", expand=True)

        self.cal_scrollbar = ttk.Scrollbar(right_fr, orient="vertical", command=self.cal_scroll_canvas.yview)
        self.cal_scrollbar.pack(side="right", fill="y")
        self.cal_scroll_canvas.configure(yscrollcommand=self.cal_scrollbar.set)

        self.cal_details_fr = tk.Frame(self.cal_scroll_canvas, bg=PANEL)
        self.cal_scroll_canvas.create_window((0, 0), window=self.cal_details_fr, anchor="nw", tags="self.cal_details_fr")
        
        # Guard against calendar scroll configure loop recursion
        self._updating_cal_scroll = False
        def on_cal_details_configure(e):
            if self._updating_cal_scroll:
                return
            self._updating_cal_scroll = True
            try:
                self.cal_scroll_canvas.configure(scrollregion=self.cal_scroll_canvas.bbox("all"))
            finally:
                self._updating_cal_scroll = False

        self._configuring_cal_canvas = False
        def on_cal_canvas_configure(e):
            if self._configuring_cal_canvas:
                return
            self._configuring_cal_canvas = True
            try:
                self.cal_scroll_canvas.itemconfig("self.cal_details_fr", width=e.width)
            finally:
                self._configuring_cal_canvas = False

        self.cal_details_fr.bind("<Configure>", on_cal_details_configure)
        self.cal_scroll_canvas.bind("<Configure>", on_cal_canvas_configure)

        # Mouse wheel support
        def _on_mousewheel(event):
            self.cal_scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        self.cal_scroll_canvas.bind("<Enter>", lambda e: self.cal_scroll_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.cal_scroll_canvas.bind("<Leave>", lambda e: self.cal_scroll_canvas.unbind_all("<MouseWheel>"))

    def _cal_prev_month(self):
        if self.cal_month == 1:
            self.cal_month = 12
            self.cal_year -= 1
        else:
            self.cal_month -= 1
        self._update_calendar()
        self._update_details()

    def _cal_next_month(self):
        if self.cal_month == 12:
            self.cal_month = 1
            self.cal_year += 1
        else:
            self.cal_month += 1
        self._update_calendar()
        self._update_details()

    def _parse_date_str(self, date_str):
        if not date_str or not isinstance(date_str, str):
            return None
        m = re.search(r"([0-9]{2})-([0-9]{2})-([0-9]{4})", date_str)
        if m:
            try:
                day, month, year = map(int, m.groups())
                return datetime(year, month, day).date()
            except ValueError:
                return None
        return None

    def _get_events_for_date(self, target_date):
        events = []
        for r in self._records:
            sd = self._parse_date_str(r.get("start_date"))
            ed = self._parse_date_str(r.get("end_date"))
            bo = self._parse_date_str(r.get("bid_opening"))
            
            if sd and sd == target_date:
                events.append(("start", r))
            if ed and ed == target_date:
                events.append(("end", r))
            if bo and bo == target_date:
                events.append(("opening", r))
        return events

    def _update_calendar(self):
        self.cal_month_lbl.configure(text=f"{calendar.month_name[self.cal_month]} {self.cal_year}")
        
        for frame in self.cal_day_frames:
            try: frame.destroy()
            except: pass
        self.cal_day_frames.clear()

        c = calendar.Calendar(firstweekday=calendar.MONDAY)
        try:
            weeks = c.monthdatescalendar(self.cal_year, self.cal_month)
        except Exception as e:
            self._log("err", f"Calendar generation error: {e}")
            return

        for r_idx, week in enumerate(weeks, 1):
            for c_idx, dt in enumerate(week):
                is_curr = (dt.month == self.cal_month and dt.year == self.cal_year)
                card_bg = CARD if is_curr else BG
                text_color = TEXT if is_curr else MUTED
                
                day_card = tk.Frame(self.cal_grid_fr, bg=card_bg,
                                    highlightthickness=1,
                                    highlightbackground="#30363D")
                day_card.grid(row=r_idx, column=c_idx, sticky="nsew", padx=2, pady=2)
                self.cal_day_frames.append(day_card)
                
                # Check selection / today
                if dt == self.cal_selected_date:
                    day_card.configure(highlightbackground=ACCENT2, highlightthickness=2)
                elif dt == datetime.now().date():
                    day_card.configure(highlightbackground=SUCCESS, highlightthickness=2)
                    
                num_lbl = tk.Label(day_card, text=str(dt.day), font=("Segoe UI", 9, "bold"),
                                   bg=card_bg, fg=text_color)
                num_lbl.pack(anchor="ne", padx=4, pady=2)
                
                events = self._get_events_for_date(dt)
                
                for evt in events[:2]:
                    evt_type, r = evt
                    bid = r.get("bid_no", "GEM/...")
                    bid_short = bid.split("/")[-1] if "/" in bid else bid
                    txt = f"{evt_type.upper()}: {bid_short}"
                    
                    if evt_type == "end":
                        fg_c, bg_c = "#FF6B6B", "#2A1D1D"
                    elif evt_type == "opening":
                        fg_c, bg_c = SUCCESS, "#1A2E1A"
                    else:
                        fg_c, bg_c = ACCENT2, "#1A2A3A"
                        
                    evt_lbl = tk.Label(day_card, text=txt, font=("Segoe UI", 7, "bold"),
                                       bg=bg_c, fg=fg_c, anchor="w", padx=4, pady=1)
                    evt_lbl.pack(fill="x", padx=4, pady=1)
                    
                if len(events) > 2:
                    more_lbl = tk.Label(day_card, text=f"+{len(events)-2} more",
                                        font=("Segoe UI", 7, "bold"), bg=card_bg, fg=MUTED, anchor="center")
                    more_lbl.pack(fill="x", padx=4, pady=1)
                    
                def make_clickable(widget, date_val=dt):
                    widget.bind("<Button-1>", lambda e: self._select_date(date_val))
                
                make_clickable(day_card)
                for child in day_card.winfo_children():
                    make_clickable(child)

    def _select_date(self, target_date):
        self.cal_selected_date = target_date
        if target_date.month != self.cal_month or target_date.year != self.cal_year:
            self.cal_month = target_date.month
            self.cal_year = target_date.year
        self._update_calendar()
        self._update_details()

    def _update_details(self):
        for child in self.cal_details_fr.winfo_children():
            child.destroy()

        date_str = self.cal_selected_date.strftime("%A, %b %d, %Y")
        self.cal_sel_date_lbl.configure(text=f"Events for:\n{date_str}")

        events = self._get_events_for_date(self.cal_selected_date)
        if not events:
            lbl = tk.Label(self.cal_details_fr, text="No events on this day.", font=FL, bg=PANEL, fg=MUTED)
            lbl.pack(pady=20)
            return

        tenders_events = {}
        for evt_type, r in events:
            bid_no = r.get("bid_no", "GEM/...")
            if bid_no not in tenders_events:
                tenders_events[bid_no] = {"rec": r, "types": []}
            tenders_events[bid_no]["types"].append(evt_type)

        for bid_no, val in tenders_events.items():
            rec = val["rec"]
            types = val["types"]
            
            card_fr = tk.Frame(self.cal_details_fr, bg=CARD, highlightthickness=1, highlightbackground="#30363D", padx=10, pady=8)
            card_fr.pack(fill="x", padx=10, pady=5)
            
            tk.Label(card_fr, text=rec.get("bid_no","GEM/..."), font=("Segoe UI", 9, "bold"), bg=CARD, fg=TEXT, anchor="w").pack(fill="x")
            
            items = rec.get("items", rec.get("category", "N/A"))
            if len(items) > 60:
                items = items[:57] + "..."
            tk.Label(card_fr, text=items, font=("Segoe UI", 8), bg=CARD, fg=TEXTSUB, anchor="w", justify="left", wraplength=260).pack(fill="x", pady=2)
            
            tags_row = tk.Frame(card_fr, bg=CARD)
            tags_row.pack(fill="x", pady=2)
            for t in types:
                if t == "end":
                    lbl_text, fg, bg = "DEADLINE / END", "#FF6B6B", "#2A1D1D"
                elif t == "opening":
                    lbl_text, fg, bg = "BID OPENING", SUCCESS, "#1A2E1A"
                else:
                    lbl_text, fg, bg = "START DATE", ACCENT2, "#1A2A3A"
                tk.Label(tags_row, text=lbl_text, font=("Segoe UI", 7, "bold"), bg=bg, fg=fg, padx=4, pady=1).pack(side="left", padx=(0,4))
                
            dates_fr = tk.Frame(card_fr, bg=CARD)
            dates_fr.pack(fill="x", pady=2)
            
            def add_date_row(lbl, val):
                if val:
                    r_fr = tk.Frame(dates_fr, bg=CARD)
                    r_fr.pack(fill="x")
                    tk.Label(r_fr, text=lbl, font=("Segoe UI", 8), bg=CARD, fg=MUTED, width=10, anchor="w").pack(side="left")
                    tk.Label(r_fr, text=val, font=("Segoe UI", 8), bg=CARD, fg=TEXTSUB, anchor="w").pack(side="left")
                    
            add_date_row("End Date:", rec.get("end_date"))
            add_date_row("Opening:", rec.get("bid_opening"))
            add_date_row("Start Date:", rec.get("start_date"))
            
            act_fr = tk.Frame(card_fr, bg=CARD)
            act_fr.pack(fill="x", pady=(6, 0))
            
            if rec.get("bid_url"):
                def make_open_url(url=rec["bid_url"]):
                    return lambda: webbrowser.open(url)
                self._btn(act_fr, "🌐 Open URL", make_open_url(), bg=PANEL).pack(side="left")
                
            def make_locate(bid=rec.get("bid_no")):
                return lambda: self._locate_in_table(bid)
            self._btn(act_fr, "🔍 Locate", make_locate(), bg=PANEL).pack(side="right")

    def _locate_in_table(self, bid):
        self.notebook.select(self.tab_table)
        for iid in self.tv.get_children():
            if self.tv.set(iid, "bid_no") == bid:
                self.tv.selection_set(iid)
                self.tv.focus(iid)
                self.tv.see(iid)
                break
