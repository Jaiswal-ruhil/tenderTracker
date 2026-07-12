import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
import calendar
import webbrowser

# Local imports
from config import (
    BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN, SEL_BG,
    FL, FB, FT, TV_IDS
)
import db

class CalendarTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app

        # Build UI layout
        self.cal_pane = tk.PanedWindow(self, orient="horizontal", bg=BG,
                                       sashwidth=4, sashrelief="flat", handlesize=0)
        self.cal_pane.pack(fill="both", expand=True, padx=4, pady=4)

        # LEFT PANEL: Calendar Grid Container
        left_fr = tk.Frame(self.cal_pane, bg=BG)
        self.cal_pane.add(left_fr, minsize=500, stretch="always")

        # Month Navigation Bar
        nav_fr = tk.Frame(left_fr, bg=PANEL, pady=8, padx=12,
                          highlightthickness=1, highlightbackground="#30363D")
        nav_fr.pack(fill="x", pady=(0, 6))

        self.cal_prev_btn = self.app._btn(nav_fr, "  ◀  ", self.cal_prev_month, bg=CARD)
        self.cal_prev_btn.pack(side="left")

        self.cal_month_lbl = tk.Label(nav_fr, text="", font=FT, bg=PANEL, fg=TEXT)
        self.cal_month_lbl.pack(side="left", expand=True)

        self.cal_next_btn = self.app._btn(nav_fr, "  ▶  ", self.cal_next_month, bg=CARD)
        self.cal_next_btn.pack(side="right")

        # Grid of Days (Mon to Sun headers + 6 weeks of cards)
        self.cal_grid_fr = tk.Frame(left_fr, bg=BG)
        self.cal_grid_fr.pack(fill="both", expand=True)

        # Weekdays headers
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for idx, day in enumerate(weekdays):
            self.cal_grid_fr.columnconfigure(idx, weight=1, uniform="daycol")
            lbl = tk.Label(self.cal_grid_fr, text=day[:3].upper(), font=("Segoe UI", 9, "bold"),
                           bg=BG, fg=MUTED, pady=6)
            lbl.grid(row=0, column=idx, sticky="ew")

        # 6 rows for weeks
        for r in range(1, 7):
            self.cal_grid_fr.rowconfigure(r, weight=1, uniform="weekrow")

        # RIGHT PANEL: Details Sidebar
        right_fr = tk.Frame(self.cal_pane, bg=PANEL, highlightthickness=1, highlightbackground="#30363D")
        self.cal_pane.add(right_fr, minsize=280, width=320, stretch="never")

        # Selected Date Label Header
        self.cal_sel_date_lbl = tk.Label(right_fr, text="", font=("Segoe UI", 10, "bold"),
                                         bg=PANEL, fg=ACCENT2, pady=10, wraplength=300)
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

        # Bind scroll events
        def _on_mousewheel(event):
            if event.num == 5 or event.delta < 0:
                self.cal_scroll_canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                self.cal_scroll_canvas.yview_scroll(-1, "units")
        
        self.cal_scroll_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.cal_scroll_canvas.bind_all("<Button-4>", _on_mousewheel)
        self.cal_scroll_canvas.bind_all("<Button-5>", _on_mousewheel)

    def cal_prev_month(self):
        if self.app.cal_month == 1:
            self.app.cal_month = 12
            self.app.cal_year -= 1
        else:
            self.app.cal_month -= 1
        self.update_calendar()
        self.update_details()

    def cal_next_month(self):
        if self.app.cal_month == 12:
            self.app.cal_month = 1
            self.app.cal_year += 1
        else:
            self.app.cal_month += 1
        self.update_calendar()
        self.update_details()

    @staticmethod
    def _parse_date_str(date_str):
        if not date_str or not isinstance(date_str, str):
            return None
        date_str = date_str.strip()
        
        m1 = re.search(r"\b([0-9]{1,2})[-/]([0-9]{1,2})[-/]([0-9]{4})\b", date_str)
        if m1:
            try:
                day, month, year = map(int, m1.groups())
                return datetime(year, month, day).date()
            except ValueError:
                pass
                
        m2 = re.search(r"\b([0-9]{4})[-/]([0-9]{1,2})[-/]([0-9]{1,2})\b", date_str)
        if m2:
            try:
                year, month, day = map(int, m2.groups())
                return datetime(year, month, day).date()
            except ValueError:
                pass
                
        return None

    def get_events_for_date(self, target_date, inc_kws=None, exc_kws=None):
        if inc_kws is None or exc_kws is None:
            settings = db.load_settings()
            inc_raw = settings.get("include_keywords", "")
            exc_raw = settings.get("exclude_keywords", "")
            inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
            exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]

        events = []
        for r in self.app._records:
            # We want to use TableTab's get_tender_status for keyword/firm logic consistency
            is_want = self.app.table_tab.get_tender_status(r, inc_kws, exc_kws)
            if not is_want:
                continue

            # Start Date
            sd_str = r.get("start_date", "")
            if sd_str:
                sd = self._parse_date_str(sd_str)
                if sd == target_date:
                    events.append(("start", r))

            # End Date (Deadline)
            ed_str = r.get("end_date", "")
            if ed_str:
                ed = self._parse_date_str(ed_str)
                if ed == target_date:
                    events.append(("end", r))

            # Bid Opening
            op_str = r.get("bid_opening", "")
            if op_str:
                op = self._parse_date_str(op_str)
                if op == target_date:
                    events.append(("opening", r))

        return events

    def update_calendar(self):
        self.cal_month_lbl.configure(text=f"{calendar.month_name[self.app.cal_month]} {self.app.cal_year}".upper())
        
        for frame in self.app.cal_day_frames:
            try: frame.destroy()
            except: pass
        self.app.cal_day_frames.clear()

        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]

        c = calendar.Calendar(firstweekday=calendar.MONDAY)
        try:
            weeks = c.monthdatescalendar(self.app.cal_year, self.app.cal_month)
        except Exception as e:
            self.app._log("err", f"Calendar generation error: {e}")
            return

        for r_idx, week in enumerate(weeks, 1):
            for c_idx, dt in enumerate(week):
                is_curr = (dt.month == self.app.cal_month and dt.year == self.app.cal_year)
                card_bg = CARD if is_curr else BG
                text_color = TEXT if is_curr else MUTED
                
                day_card = tk.Frame(self.cal_grid_fr, bg=card_bg,
                                    highlightthickness=1,
                                    highlightbackground="#30363D")
                day_card.grid(row=r_idx, column=c_idx, sticky="nsew", padx=2, pady=2)
                self.app.cal_day_frames.append(day_card)
                
                if dt == self.app.cal_selected_date:
                    day_card.configure(highlightbackground=ACCENT2, highlightthickness=2)
                elif dt == datetime.now().date():
                    day_card.configure(highlightbackground=SUCCESS, highlightthickness=2)
                    
                num_lbl = tk.Label(day_card, text=str(dt.day), font=("Segoe UI", 9, "bold"),
                                   bg=card_bg, fg=text_color)
                num_lbl.pack(anchor="ne", padx=6, pady=3)
                
                events = self.get_events_for_date(dt, inc_kws, exc_kws)
                
                for evt in events[:2]:
                    evt_type, r = evt
                    bid = r.get("bid_no", "GEM/...")
                    bid_short = bid.split("/")[-1] if "/" in bid else bid
                    txt = f" {evt_type.upper()[:5]}: {bid_short}"
                    
                    if evt_type == "end":
                        fg_c, bg_c = "#FF6B6B", "#2D1E1E"
                    elif evt_type == "opening":
                        fg_c, bg_c = SUCCESS, "#1E2D1E"
                    else:
                        fg_c, bg_c = ACCENT2, "#1D2837"
                        
                    evt_lbl = tk.Label(day_card, text=txt, font=("Segoe UI", 7, "bold"),
                                       bg=bg_c, fg=fg_c, anchor="w", padx=4, pady=2)
                    evt_lbl.pack(fill="x", padx=4, pady=1)
                    
                if len(events) > 2:
                    more_lbl = tk.Label(day_card, text=f"+{len(events)-2} MORE",
                                        font=("Segoe UI", 7, "bold"), bg=card_bg, fg=MUTED, anchor="center")
                    more_lbl.pack(fill="x", padx=4, pady=2)

                # Smooth hover highlights
                def on_enter(event, card=day_card, original_bg=card_bg):
                    hover_bg = "#2C313C" if original_bg == CARD else "#1C212D"
                    card.configure(bg=hover_bg)
                    for child in card.winfo_children():
                        if child.cget("bg") == original_bg:
                            child.configure(bg=hover_bg)

                def on_leave(event, card=day_card, original_bg=card_bg):
                    card.configure(bg=original_bg)
                    for child in card.winfo_children():
                        if child.cget("bg") in ("#2C313C", "#1C212D"):
                            child.configure(bg=original_bg)

                day_card.bind("<Enter>", on_enter)
                day_card.bind("<Leave>", on_leave)

                def make_clickable(widget, date_val=dt):
                    widget.bind("<Button-1>", lambda e: self.select_date(date_val))
                
                make_clickable(day_card)
                for child in day_card.winfo_children():
                    make_clickable(child)

    def select_date(self, target_date):
        self.app.cal_selected_date = target_date
        if target_date.month != self.app.cal_month or target_date.year != self.app.cal_year:
            self.app.cal_month = target_date.month
            self.app.cal_year = target_date.year
        self.update_calendar()
        self.update_details()

    def update_details(self):
        for child in self.cal_details_fr.winfo_children():
            child.destroy()

        date_str = self.app.cal_selected_date.strftime("%A, %b %d, %Y")
        self.cal_sel_date_lbl.configure(text=f"EVENTS FOR:\n{date_str}".upper())

        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]

        events = self.get_events_for_date(self.app.cal_selected_date, inc_kws, exc_kws)
        if not events:
            lbl = tk.Label(self.cal_details_fr, text="No events on this day.", font=FL, bg=PANEL, fg=MUTED)
            lbl.pack(pady=30)
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
            
            card_fr = tk.Frame(self.cal_details_fr, bg=CARD, highlightthickness=1, highlightbackground="#30363D", padx=12, pady=10)
            card_fr.pack(fill="x", padx=10, pady=6)
            
            tk.Label(card_fr, text=rec.get("bid_no","GEM/..."), font=("Segoe UI", 9, "bold"), bg=CARD, fg=TEXT, anchor="w").pack(fill="x")
            
            items = rec.get("items", rec.get("category", "N/A"))
            if len(items) > 70:
                items = items[:67] + "..."
            tk.Label(card_fr, text=items, font=("Segoe UI", 8), bg=CARD, fg=TEXTSUB, anchor="w", justify="left", wraplength=250).pack(fill="x", pady=2)
            
            tags_row = tk.Frame(card_fr, bg=CARD)
            tags_row.pack(fill="x", pady=4)
            for t in types:
                if t == "end":
                    lbl_text, fg, bg = "DEADLINE / END", "#FF6B6B", "#2D1E1E"
                elif t == "opening":
                    lbl_text, fg, bg = "BID OPENING", SUCCESS, "#1E2D1E"
                else:
                    lbl_text, fg, bg = "START DATE", ACCENT2, "#1D2837"
                tk.Label(tags_row, text=lbl_text, font=("Segoe UI", 7, "bold"), bg=bg, fg=fg, padx=5, pady=2).pack(side="left", padx=(0,4))
                
            dates_fr = tk.Frame(card_fr, bg=CARD)
            dates_fr.pack(fill="x", pady=2)
            
            def add_date_row(lbl, val):
                if val:
                    r_fr = tk.Frame(dates_fr, bg=CARD)
                    r_fr.pack(fill="x")
                    tk.Label(r_fr, text=lbl, font=("Segoe UI", 8), bg=CARD, fg=MUTED, width=11, anchor="w").pack(side="left")
                    tk.Label(r_fr, text=val, font=("Segoe UI", 8), bg=CARD, fg=TEXTSUB, anchor="w").pack(side="left")
                    
            add_date_row("End Date:", rec.get("end_date"))
            add_date_row("Opening:", rec.get("bid_opening"))
            add_date_row("Start Date:", rec.get("start_date"))
            
            act_fr = tk.Frame(card_fr, bg=CARD)
            act_fr.pack(fill="x", pady=(8, 0))
            
            if rec.get("bid_url"):
                def make_open_url(url=rec["bid_url"]):
                    return lambda: webbrowser.open(url)
                self.app._btn(act_fr, "🌐 Open URL", make_open_url(), bg=PANEL).pack(side="left")
                
            pdf_path = rec.get("pdf_path")
            if pdf_path and os.path.exists(pdf_path):
                def make_open_pdf(path=pdf_path):
                    import sys
                    import subprocess
                    from tkinter import messagebox
                    def open_fn():
                        try:
                            if sys.platform == "win32":
                                os.startfile(path)
                            elif sys.platform == "darwin":
                                subprocess.run(["open", path])
                            else:
                                subprocess.run(["xdg-open", path])
                            self.app._log("ok", f"Opened PDF: {os.path.basename(path)}")
                        except Exception as e:
                            try:
                                webbrowser.open(f"file:///{os.path.abspath(path)}")
                                self.app._log("ok", f"Opened PDF in browser: {os.path.basename(path)}")
                            except Exception as ex:
                                self.app._log("err", f"Failed to open PDF: {e}")
                                messagebox.showerror("Open Error", f"Could not open PDF file:\n{e}")
                    return open_fn
                self.app._btn(act_fr, "📄 Open PDF", make_open_pdf(), bg=PANEL).pack(side="left", padx=(6, 0))
                
            def make_locate(bid=rec.get("bid_no")):
                return lambda: self.locate_in_table(bid)
            self.app._btn(act_fr, "🔍 Locate", make_locate(), bg=PANEL).pack(side="right")

    def locate_in_table(self, bid):
        self.app.notebook.select(self.app.tab_table)
        
        # Clear search and filters to ensure the target bid is actually visible in the treeview
        filter_changed = False
        if hasattr(self.app, "view_var") and self.app.view_var.get() != "All Tenders":
            self.app.view_var.set("All Tenders")
            filter_changed = True
        if hasattr(self.app, "status_view_var") and self.app.status_view_var.get() != "All":
            self.app.status_view_var.set("All")
            filter_changed = True
        if hasattr(self.app, "date_filter_preset_var") and self.app.date_filter_preset_var.get() != "All Dates":
            self.app.date_filter_preset_var.set("All Dates")
            self.app._apply_date_filter_preset(initial=False)
            filter_changed = True
        if hasattr(self.app, "search_var") and self.app.search_var.get().strip():
            self.app.search_var.set("")
            filter_changed = True
            
        if filter_changed:
            self.app._refresh_table_view()
            
        for iid in self.app.tv.get_children():
            if self.app.tv.set(iid, "bid_no") == bid:
                self.app.tv.selection_set(iid)
                self.app.tv.focus(iid)
                self.app.tv.see(iid)
                break
