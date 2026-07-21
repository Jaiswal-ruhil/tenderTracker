import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, date, timedelta

# Local imports
from config import (
    BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN, SEL_BG,
    FL, FB, FT, TV_COLS, TV_IDS, URGENT_BG, WARN_BG, CLOSED_FG
)
from excel import financial_year, xl_path, ensure_workbook, xl_append
import db
from vector_search import semantic_search
import filing_workflow

from components.table_view import TendersTableView
from components.side_panel import TenderDetailPanel
from components.right_click_menu import TenderContextMenu

class TableTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app

        # State Variables (exposed on TableTab, then mapped on TenderApp for compatibility)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh_table_view())
        
        self.semantic_search_var = tk.BooleanVar(value=False)
        self.view_var = tk.StringVar(value="Wants (Matches)")
        self.status_view_var = tk.StringVar(value="All")
        self.date_filter_type_var = tk.StringVar(value="None")
        self.date_filter_preset_var = tk.StringVar(value="All Dates")
        self.date_from_var = tk.StringVar()
        self.date_from_var.trace_add("write", lambda *args: self.refresh_table_view())
        self.date_to_var = tk.StringVar()
        self.date_to_var.trace_add("write", lambda *args: self.refresh_table_view())

        self._build_ui()
        self._apply_date_filter_preset(initial=True)

    def _build_ui(self):
        # Table Tab Header
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", pady=(4, 4))
        tk.Label(hdr, text="Parsed Tenders", font=("Segoe UI", 9, "bold"), bg=BG, fg=MUTED).pack(side="left")
        
        self.count_lbl = tk.Label(hdr, text="0 rows", font=FL, bg=BG, fg=TEXTSUB)
        self.count_lbl.pack(side="left", padx=8)

        self.app._btn(hdr, "Select All",      self.sel_all,    bg=CARD).pack(side="right", padx=2)
        self.app._btn(hdr, "Delete Selected", self.del_sel,    bg=CARD, fg=ERR).pack(side="right", padx=2)
        self.app._btn(hdr, "  Fetch Selected (Selenium)  ", self.app._do_fetch_sel, bg="#2D333B").pack(side="right", padx=2)
        self.app._btn(hdr, "  Process Local PDFs  ", self.app._do_process_local_pdfs, bg="#2D333B").pack(side="right", padx=2)
        self.app._btn(hdr, "  Save Selected to Excel  ", self.save_selected, bg=ACCENT, pad=10).pack(side="right", padx=(6, 2))

        summary_fr = tk.Frame(self, bg=PANEL, padx=10, pady=6, highlightthickness=1, highlightbackground="#30363D")
        summary_fr.pack(fill="x", pady=(0, 6))
        self.table_summary_lbl = tk.Label(
            summary_fr,
            text="Visible: 0   Wants: 0   Not Filed: 0   Firm Matched: 0",
            font=("Segoe UI", 8, "bold"),
            bg=PANEL,
            fg=TEXTSUB,
            anchor="w"
        )
        self.table_summary_lbl.pack(fill="x")

        # ── Filter & Refine Bar ──────────────────────────────────────────────
        filter_fr = tk.Frame(self, bg=PANEL, padx=10, pady=6, highlightthickness=1, highlightbackground="#30363D")
        filter_fr.pack(fill="x", pady=(0, 6))

        # Search box
        tk.Label(filter_fr, text="Search:", font=FL, bg=PANEL, fg=MUTED).pack(side="left")
        self.search_ent = tk.Entry(filter_fr, textvariable=self.search_var, bg=CARD, fg=TEXT,
                                  insertbackground=TEXT, relief="flat", font=FL, width=22,
                                  highlightthickness=1, highlightbackground="#30363D",
                                  highlightcolor=ACCENT2)
        self.search_ent.pack(side="left", padx=(4, 15))

        # Semantic Search Checkbox
        self.semantic_search_cb = tk.Checkbutton(
            filter_fr, text="Semantic Search", variable=self.semantic_search_var,
            bg=PANEL, fg=TEXT, selectcolor=CARD, activebackground=PANEL, activeforeground=TEXT,
            font=FL, command=self.refresh_table_view
        )
        self.semantic_search_cb.pack(side="left", padx=(0, 15))

        # View dropdown
        tk.Label(filter_fr, text="Filter:", font=FL, bg=PANEL, fg=MUTED).pack(side="left")
        view_opt = ttk.Combobox(filter_fr, textvariable=self.view_var, 
                                values=["All Tenders", "Wants (Matches)", "Don't Wants (Filtered)"],
                                state="readonly", font=FL, width=20)
        view_opt.pack(side="left", padx=4)
        view_opt.bind("<<ComboboxSelected>>", lambda e: self.refresh_table_view())

        # Visual separator
        tk.Label(filter_fr, text="│", font=FL, bg=PANEL, fg="#30363D").pack(side="left", padx=(6, 6))

        # Status View dropdown
        tk.Label(filter_fr, text="Status:", font=FL, bg=PANEL, fg=MUTED).pack(side="left")
        status_view_opt = ttk.Combobox(filter_fr, textvariable=self.status_view_var,
                                       values=["All", "To Be Filed", "Evaluating", "Filed"],
                                       state="readonly", font=FL, width=13)
        status_view_opt.pack(side="left", padx=4)
        status_view_opt.bind("<<ComboboxSelected>>", lambda e: self.refresh_table_view())
        
        # Date Filter in Table View
        tk.Label(filter_fr, text="Date Filter:", font=FL, bg=PANEL, fg=MUTED).pack(side="left", padx=(10, 0))
        self.date_filter_combo = ttk.Combobox(
            filter_fr, textvariable=self.date_filter_preset_var,
            values=[
                "All Dates",
                "End Date: Today",
                "End Date: Tomorrow",
                "End Date: Next 3 Days",
                "End Date: This Week",
                "End Date: Custom..."
            ],
            state="readonly", font=FL, width=20
        )
        self.date_filter_combo.pack(side="left", padx=4)
        self.date_filter_combo.bind("<<ComboboxSelected>>", lambda e: self.on_date_combo_changed())

        # Custom date range entry frame (hidden by default)
        self.custom_date_frame = tk.Frame(filter_fr, bg=PANEL)
        
        tk.Label(self.custom_date_frame, text="From:", font=FL, bg=PANEL, fg=MUTED).pack(side="left", padx=(4, 2))
        self.date_from_ent = tk.Entry(self.custom_date_frame, textvariable=self.date_from_var, bg=CARD, fg=TEXT,
                                      insertbackground=TEXT, relief="flat", font=FL, width=10,
                                      highlightthickness=1, highlightbackground="#30363D")
        self.date_from_ent.pack(side="left")
        
        self.btn_from_cal = tk.Button(self.custom_date_frame, text="📅", bg=CARD, fg=TEXT, relief="flat",
                                      font=("Segoe UI", 9), padx=4, pady=0, cursor="hand2",
                                      activebackground=ACCENT)
        self.btn_from_cal.pack(side="left", padx=(2, 6))
        self.btn_from_cal.configure(command=lambda: self._show_datepicker(self.btn_from_cal, self.date_from_var))

        tk.Label(self.custom_date_frame, text="To:", font=FL, bg=PANEL, fg=MUTED).pack(side="left", padx=(4, 2))
        self.date_to_ent = tk.Entry(self.custom_date_frame, textvariable=self.date_to_var, bg=CARD, fg=TEXT,
                                    insertbackground=TEXT, relief="flat", font=FL, width=10,
                                    highlightthickness=1, highlightbackground="#30363D")
        self.date_to_ent.pack(side="left")

        self.btn_to_cal = tk.Button(self.custom_date_frame, text="📅", bg=CARD, fg=TEXT, relief="flat",
                                    font=("Segoe UI", 9), padx=4, pady=0, cursor="hand2",
                                    activebackground=ACCENT)
        self.btn_to_cal.pack(side="left", padx=(2, 6))
        self.btn_to_cal.configure(command=lambda: self._show_datepicker(self.btn_to_cal, self.date_to_var))

        # Refine rules and copy table buttons
        self.app._btn(filter_fr, "⚙ Refine Rules...", self.app._show_filter_rules_dialog, bg=CARD).pack(side="right")
        self.app._btn(filter_fr, "👁 Select Columns...", self.show_column_selector, bg=CARD).pack(side="right", padx=(0, 6))
        self.app._btn(filter_fr, "📋 Copy Table", self.copy_table_output, bg=CARD).pack(side="right", padx=(0, 6))

        # Create PanedWindow for Table and Details Sidebar
        self.table_pane = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=4, sashrelief="flat", handlesize=0)
        self.table_pane.pack(fill="both", expand=True)

        # 1. Left Pane: Table View
        self.table_view = TendersTableView(self.table_pane, self.app, self)
        self.table_pane.add(self.table_view, minsize=400, stretch="always")
        self.tv = self.table_view.tv  # Alias for backward compatibility

        # 2. Right Pane: Detail Panel
        self.detail_panel = TenderDetailPanel(self.table_pane, self.app, self)
        self.table_pane.add(self.detail_panel, minsize=320, stretch="always")

        # 3. Context Menu
        self.context_menu = TenderContextMenu(self, self.app, self)
        self.tv.bind("<Button-3>", self.context_menu.show)
        self.tv.bind("<Button-2>", self.context_menu.show)  # For macOS

        self.apply_column_visibility()

    def _show_datepicker(self, button, var):
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        from components.date_picker import DatePickerPopup
        DatePickerPopup(self.app, var, x, y)

    @staticmethod
    def _stem_word(w):
        """Simple English suffix stemmer for keyword normalization."""
        w = w.lower()
        for sfx in ("ings", "ing", "tion", "tions", "ies", "es", "s"):
            if w.endswith(sfx) and len(w) - len(sfx) >= 3:
                return w[: -len(sfx)]
        return w

    @staticmethod
    def _parse_date_str(date_str):
        if not date_str or not isinstance(date_str, str):
            return None
        date_str = date_str.strip()
        
        # 1. Try DD-MM-YYYY or DD/MM/YYYY with 1 or 2 digit day/month
        m1 = re.search(r"\b([0-9]{1,2})[-/]([0-9]{1,2})[-/]([0-9]{4})\b", date_str)
        if m1:
            try:
                day, month, year = map(int, m1.groups())
                return datetime(year, month, day).date()
            except ValueError:
                pass
                
        # 2. Try YYYY-MM-DD or YYYY/MM/DD with 1 or 2 digit day/month
        m2 = re.search(r"\b([0-9]{4})[-/]([0-9]{1,2})[-/]([0-9]{1,2})\b", date_str)
        if m2:
            try:
                year, month, day = map(int, m2.groups())
                return datetime(year, month, day).date()
            except ValueError:
                pass
                
        return None

    def get_tender_status(self, rec, inc_kws, exc_kws, settings=None):
        is_want = rec.get("is_want")
        if is_want is not None:
            return is_want

        items_raw = str(rec.get("items", ""))
        if items_raw.endswith("..."):
            items_raw = items_raw[:-3].strip()

        search_fields = [
            items_raw,
            rec.get("category", ""),
            rec.get("ministry", ""),
            rec.get("dept", ""),
            rec.get("organisation", ""),
            rec.get("location", ""),
            rec.get("bid_no", "")
        ]
        combined_text = " ".join(str(f) for f in search_fields).lower()
        stemmed_text = " ".join(self._stem_word(w) for w in combined_text.split())

        def check_single_rule(rule):
            rule_clean = rule.strip()
            if not rule_clean:
                return False

            if rule_clean.lower().startswith("rx:"):
                pattern = rule_clean[3:].strip()
                try:
                    return bool(re.search(pattern, combined_text, re.I))
                except Exception:
                    return False

            if " and " in rule_clean.lower() or " or " in rule_clean.lower() \
                    or "not " in rule_clean.lower() or "(" in rule_clean:
                return eval_expr(rule_clean.lower())

            if rule_clean.isalnum() and len(rule_clean) <= 3:
                pattern = r"\b" + re.escape(rule_clean.lower()) + r"\b"
                return bool(re.search(pattern, combined_text, re.I))

            kw_lower = rule_clean.lower()
            if kw_lower in combined_text:
                return True
            kw_stemmed = self._stem_word(kw_lower)
            if len(kw_stemmed) >= 4 and kw_stemmed in stemmed_text:
                return True
            return False

        def eval_expr(expr):
            parts = re.split(r"(\(|\)|\bnot\b|\band\b|\bor\b)", expr, flags=re.I)
            processed_tokens = []
            for p in parts:
                if p is None:
                    continue
                p_clean = p.strip()
                if not p_clean:
                    continue
                if p_clean.lower() in ("(", ")", "and", "or", "not"):
                    processed_tokens.append(p_clean.lower())
                else:
                    exists = check_single_rule(p_clean)
                    processed_tokens.append("True" if exists else "False")
            
            expr_str = " ".join(processed_tokens)
            expr_str = re.sub(r"[^a-zA-Z0-9\s()&|!]", "", expr_str)
            try:
                if re.match(r"^[TrueFalse()andornot\s]+$", expr_str):
                    return bool(eval(expr_str))
            except Exception:
                pass
            return False

        if settings is None:
            settings = db.load_settings()
        firms = settings.get("firms", [])
        if firms:
            matched_firms = []
            for firm in firms:
                exc_raw = firm.get("exclude_keywords", "")
                exc_list = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
                is_excluded = False
                for kw in exc_list:
                    if check_single_rule(kw):
                        is_excluded = True
                        break
                if is_excluded:
                    continue
                    
                cats_val = firm.get("categories", [])
                cat_list = []
                if cats_val:
                    if isinstance(cats_val, list):
                        cat_list = [c.lower() for c in cats_val]
                    elif isinstance(cats_val, str):
                        cat_list = [c.strip().lower() for c in cats_val.split(",") if c.strip()]
                
                cat_match = False
                matched_kw = ""
                if cat_list:
                    for kw in cat_list:
                        if check_single_rule(kw):
                            cat_match = True
                            matched_kw = kw
                            break
                else:
                    cat_match = True
                    
                if not cat_match:
                    continue
                    
                loc_raw = firm.get("locations", "")
                loc_list = [k.strip().lower() for k in loc_raw.split(",") if k.strip()]
                loc_match = False
                if loc_list:
                    for kw in loc_list:
                        if check_single_rule(kw):
                            loc_match = True
                            break
                else:
                    loc_match = True
                    
                if not loc_match:
                    continue
                    
                matched_firms.append(firm.get("name", "Unnamed Firm"))
                if matched_kw:
                    rec["matched_keyword"] = matched_kw

            if matched_firms:
                rec["matched_firm"] = ", ".join(matched_firms)
                return True
            else:
                rec["matched_firm"] = ""
                rec.setdefault("matched_keyword", "")
                return False

        rec["matched_firm"] = ""
        matches_exc = False
        for rule in exc_kws:
            if check_single_rule(rule):
                matches_exc = True
                break
                
        if matches_exc:
            if inc_kws:
                for rule in inc_kws:
                    if check_single_rule(rule):
                        return True
            return False
            
        if inc_kws:
            for rule in inc_kws:
                if check_single_rule(rule):
                    return True
            return False
            
        return True

    def is_bid_in_dont_wants(self, bid_no_or_id):
        if not bid_no_or_id:
            return False
        target = bid_no_or_id.strip().lower()
        
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]

        for r in self.app._records:
            r_bid_no = r.get("bid_no", "").strip().lower()
            r_bid_url = r.get("bid_url", "").strip().lower()
            
            match = False
            if target == r_bid_no:
                match = True
            elif target in r_bid_url:
                match = True
            elif "/" in r_bid_no and target == r_bid_no.split("/")[-1]:
                match = True
                
            if match:
                is_want = self.get_tender_status(r, inc_kws, exc_kws, settings=settings)
                if not is_want:
                    return r
        return None

    def refresh_table_view(self):
        import threading
        if threading.current_thread() is not threading.main_thread():
            self.app.after(0, self.refresh_table_view)
            return

        if not hasattr(self, "table_view") or self.table_view is None:
            return
        for child in self.table_view.tv.get_children():
            self.table_view.tv.delete(child)
            
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
        
        view_filter = self.view_var.get()
        search_text = self.search_var.get().strip().lower()
        
        # Load Date Filters
        date_filter_type = self.date_filter_type_var.get()
        from_date_parsed = self._parse_date_str(self.date_from_var.get().strip())
        to_date_parsed = self._parse_date_str(self.date_to_var.get().strip())
        
        # Determine if semantic search is active
        is_semantic = self.semantic_search_var.get() and search_text
        semantic_ranks = {}
        if is_semantic:
            results = semantic_search(search_text, limit=100)
            semantic_ranks = {bid_no: idx for idx, (bid_no, _) in enumerate(results)}

        records_to_render = self.app._records
        if is_semantic:
            matched_recs = [r for r in self.app._records if r.get("bid_no") in semantic_ranks]
            matched_recs.sort(key=lambda r: semantic_ranks[r["bid_no"]])
            records_to_render = matched_recs
        
        visible_count = 0
        visible_wants = 0
        visible_not_filed = 0
        visible_firm_matched = 0
        for rec in records_to_render:
            is_want = self.get_tender_status(rec, inc_kws, exc_kws, settings=settings)
            rec["is_want_derived"] = is_want
            
            if view_filter == "Wants (Matches)" and not is_want:
                continue
            if view_filter == "Don't Wants (Filtered)" and is_want:
                continue

            # Apply Status View filter
            sv = self.status_view_var.get()
            if sv != "All":
                rec_status = rec.get("filing_status", "")
                if rec_status != sv:
                    continue
                
            if search_text and not is_semantic:
                combined_text = " ".join(str(v) for v in rec.values()).lower()
                if search_text not in combined_text:
                    continue
            
            # Apply Date Filtering
            if date_filter_type != "None":
                fld_map = {
                    "Start Date": "start_date",
                    "End Date": "end_date",
                    "Bid Opening Date": "bid_opening"
                }
                fld_key = fld_map.get(date_filter_type)
                if fld_key:
                    bid_date_str = rec.get(fld_key)
                    bid_date = self._parse_date_str(bid_date_str)
                    if bid_date:
                        if from_date_parsed and bid_date < from_date_parsed:
                            continue
                        if to_date_parsed and bid_date > to_date_parsed:
                            continue
                    else:
                        if from_date_parsed or to_date_parsed:
                            continue
                    
            self.table_view.tv_insert(rec)
            visible_count += 1
            if is_want:
                visible_wants += 1
                if rec.get("filing_status", "Not Filed") == "Not Filed":
                    visible_not_filed += 1
            if rec.get("matched_firm", "").strip():
                visible_firm_matched += 1
            
        self.table_view.refresh_alt()
        self.count_lbl.configure(text=f"{visible_count} visible / {len(self.app._records)} total")
        self.table_summary_lbl.configure(
            text=f"Visible: {visible_count}   Wants: {visible_wants}   Not Filed: {visible_not_filed}   Firm Matched: {visible_firm_matched}"
        )

    def mark_selected_want(self):
        sel = self.tv.selection()
        if not sel: return
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self.app._records:
                    if r.get("bid_no") == bid_no:
                        r["is_want"] = True
                        break
        db.save_all_tenders(self.app._records)
        self.refresh_table_view()
        self.app._log("ok", f"Marked {len(sel)} tender(s) as Want.")

    def mark_want_and_learn(self):
        sel = self.tv.selection()
        if not sel:
            return
        bid_no = self.tv.set(sel[0], "bid_no")
        rec = next((r for r in self.app._records if r.get("bid_no") == bid_no), None)
        if not rec:
            return

        for iid in sel:
            b = self.tv.set(iid, "bid_no")
            for r in self.app._records:
                if r.get("bid_no") == b:
                    r["is_want"] = True
                    break
        db.save_all_tenders(self.app._records)
        self.app._reload()
        self.app._log("ok", f"Marked {len(sel)} tender(s) as Want.")

        items_text = str(rec.get("items", "")).replace("...", "").strip()
        words = [w.strip(",.-") for w in items_text.split() if len(w.strip(",.-")) >= 4]
        STOPWORDS = {"with", "and", "for", "the", "supply", "of", "new", "used", "size",
                     "type", "model", "make", "brand", "grade", "capacity", "nos", "sets"}
        candidates = [w for w in words if w.lower() not in STOPWORDS][:8]

        if not candidates:
            return

        dlg = tk.Toplevel(self.app)
        dlg.title("Learn Keyword")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.transient(self.app)
        dlg.geometry(f"440x320+{self.app.winfo_x()+200}+{self.app.winfo_y()+150}")

        tk.Label(dlg, text="✨ Learn from this tender", font=("Segoe UI", 11, "bold"), bg=BG, fg=TEXT).pack(pady=(16, 4))
        tk.Label(dlg, text="Select a keyword to add to the matched firm's categories:", font=FL, bg=BG, fg=MUTED, wraplength=400).pack(pady=(0, 10))

        kw_var = tk.StringVar(value=candidates[0] if candidates else "")

        btn_row = tk.Frame(dlg, bg=BG)
        btn_row.pack(fill="x", padx=20)
        for cand in candidates:
            def _pick(k=cand):
                kw_var.set(k)
                for w in btn_row.winfo_children():
                    w.configure(bg=CARD, fg=TEXTSUB)
                    if w.cget("text") == k:
                        w.configure(bg=ACCENT2, fg=TEXT)
            tk.Button(btn_row, text=cand, command=_pick,
                      bg=CARD, fg=TEXTSUB, relief="flat", font=FL,
                      padx=8, pady=4, cursor="hand2").pack(side="left", padx=(0, 6), pady=4)

        tk.Label(dlg, text="Or type custom keyword:", font=("Segoe UI", 8), bg=BG, fg=MUTED).pack(anchor="w", padx=20, pady=(10, 2))
        custom_ent = tk.Entry(dlg, textvariable=kw_var, bg=CARD, fg=TEXT,
                              insertbackground=TEXT, relief="flat", font=FL,
                              highlightthickness=1, highlightbackground="#30363D")
        custom_ent.pack(fill="x", padx=20, ipady=4)

        def _apply():
            kw = kw_var.get().strip()
            if not kw:
                dlg.destroy()
                return
            settings = db.load_settings()
            firms = settings.get("firms", [])
            target_firm = None
            mf = rec.get("matched_firm", "")
            for f in firms:
                if f.get("name") == mf or not mf:
                    target_firm = f
                    break
            if not target_firm and firms:
                target_firm = firms[0]
            if target_firm:
                cats = target_firm.get("categories", [])
                if isinstance(cats, str):
                    cats = [c.strip() for c in cats.split(",") if c.strip()]
                if kw not in cats:
                    cats.append(kw)
                    target_firm["categories"] = cats
                    db.save_setting("firms", firms)
                    self.app._log("ok", f"Learned keyword '{kw}' → added to firm '{target_firm.get('name')}'.")
                    self.app._reload()
                else:
                    self.app._log("info", f"Keyword '{kw}' already in firm categories.")
            dlg.destroy()

        bot = tk.Frame(dlg, bg=BG)
        bot.pack(fill="x", side="bottom", pady=16, padx=20)
        self.app._btn(bot, "Add Keyword & Apply", _apply, bg=ACCENT).pack(side="left")
        self.app._btn(bot, "Skip", dlg.destroy, bg=CARD).pack(side="left", padx=(8, 0))

    def mark_selected_dont_want(self):
        sel = self.tv.selection()
        if not sel: return
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self.app._records:
                    if r.get("bid_no") == bid_no:
                        r["is_want"] = False
                        break
        db.save_all_tenders(self.app._records)
        self.app._reload()
        self.app._log("ok", f"Marked {len(sel)} tender(s) as Don't Want.")

    def reset_selected_tag(self):
        sel = self.tv.selection()
        if not sel: return
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self.app._records:
                    if r.get("bid_no") == bid_no:
                        r.pop("is_want", None)
                        break
        db.save_all_tenders(self.app._records)
        self.app._reload()
        self.app._log("info", f"Reset manual tag for {len(sel)} tender(s).")

    def set_selected_filing_status(self, status):
        sel = self.tv.selection()
        if not sel:
            return
        updated_count = 0
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self.app._records:
                    if r.get("bid_no") == bid_no:
                        r["filing_status"] = status
                        updated_count += 1
                        break
                self.tv.set(iid, "filing_status", status)
                db.upsert_tender_field(bid_no, "filing_status", status)
                
        if updated_count > 0:
            self.app._log("ok", f"Set filing status to '{status}' for {updated_count} tender(s).")
            self.app._reload()

    # Batch operation wrappers (these methods already support multiple selections)
    def batch_mark_want(self):
        self.mark_selected_want()
    
    def batch_mark_dont_want(self):
        self.mark_selected_dont_want()
    
    def batch_set_status(self, status):
        self.set_selected_filing_status(status)
    
    def batch_delete(self):
        self.del_sel()

    def copy_table_output(self):
        headers = [c[1] for c in TV_COLS]
        lines = ["\t".join(headers)]
        
        selected = self.tv.selection()
        rows_to_copy = selected if selected else self.tv.get_children()
        
        if not rows_to_copy:
            self.app._log("warn", "No data to copy.")
            return
            
        for iid in rows_to_copy:
            vals = [str(self.tv.set(iid, c[0])) for c in TV_COLS]
            lines.append("\t".join(vals))
            
        text_to_copy = "\n".join(lines)
        self.app.clipboard_clear()
        self.app.clipboard_append(text_to_copy)
        self.app.update()
        
        count = len(rows_to_copy)
        scope = "selected" if selected else "all visible"
        self.app._log("ok", f"Copied {count} {scope} row(s) to clipboard.")

    def on_date_combo_changed(self):
        val = self.date_filter_preset_var.get()
        if val == "End Date: Custom...":
            self.custom_date_frame.pack(side="left", padx=4)
        else:
            self.custom_date_frame.pack_forget()
        self._apply_date_filter_preset()

    def _apply_date_filter_preset(self, initial=False):
        preset = self.date_filter_preset_var.get()
        today = date.today()
        
        if preset == "All Dates":
            self.date_filter_type_var.set("None")
            from_date = None
            to_date = None
        elif preset.startswith("End Date:"):
            self.date_filter_type_var.set("End Date")
            sub_preset = preset[len("End Date:"):].strip()
            if sub_preset == "Today":
                from_date = today
                to_date = today
            elif sub_preset == "Tomorrow":
                from_date = today + timedelta(days=1)
                to_date = today + timedelta(days=1)
            elif sub_preset == "Next 3 Days":
                from_date = today
                to_date = today + timedelta(days=3)
            elif sub_preset == "This Week":
                weekday = today.isoweekday()
                from_date = today
                to_date = today + timedelta(days=(7 - weekday))
            elif sub_preset == "Custom...":
                if initial:
                    self.custom_date_frame.pack(side="left", padx=4)
                if not initial:
                    self.refresh_table_view()
                return
            else:
                from_date = today
                to_date = today
        else:
            self.date_filter_type_var.set("None")
            from_date = None
            to_date = None

        self.date_from_var.set(from_date.strftime("%d-%m-%Y") if from_date else "")
        self.date_to_var.set(to_date.strftime("%d-%m-%Y") if to_date else "")
        if not initial:
            self.refresh_table_view()

    def set_dynamic_default_date_filter(self):
        """
        Dynamically determine the default date filter on startup based on record dates in wants:
        1. Set to 'End Date: Today' if there are wants ending today.
        2. Else, set to 'End Date: Tomorrow' if there are wants ending tomorrow.
        3. Else, set to 'End Date: Next 3 Days' if there are wants ending within the next 3 days.
        4. Else, set to 'All Dates'.
        """
        records = self.app._records
        if not records:
            self.date_filter_preset_var.set("All Dates")
            self._apply_date_filter_preset(initial=True)
            return

        settings = db.load_settings()
        inc_kws = settings.get("include_keywords", [])
        exc_kws = settings.get("exclude_keywords", [])

        today = date.today()
        tomorrow = today + timedelta(days=1)
        next_3_days_end = today + timedelta(days=3)

        has_today = False
        has_tomorrow = False
        has_next_3_days = False

        for rec in records:
            is_want = self.get_tender_status(rec, inc_kws, exc_kws, settings=settings)
            if not is_want:
                continue

            end_date_str = rec.get("end_date")
            if end_date_str:
                parsed_date = self._parse_date_str(end_date_str)
                if parsed_date:
                    if parsed_date == today:
                        has_today = True
                    if parsed_date == tomorrow:
                        has_tomorrow = True
                    if today <= parsed_date <= next_3_days_end:
                        has_next_3_days = True

        if has_today:
            self.date_filter_preset_var.set("End Date: Today")
        elif has_tomorrow:
            self.date_filter_preset_var.set("End Date: Tomorrow")
        elif has_next_3_days:
            self.date_filter_preset_var.set("End Date: Next 3 Days")
        else:
            self.date_filter_preset_var.set("All Dates")

        self._apply_date_filter_preset(initial=False)

    def on_treeview_select(self, event):
        self.detail_panel.on_treeview_select(event)

    def link_associated_pdf(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showwarning("Selection Required", "Please select a tender from the table first.")
            return
        bid_no = self.tv.set(sel[0], "bid_no")
        if not bid_no:
            return
            
        file_path = filedialog.askopenfilename(
            title="Select PDF File to Link",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if not file_path:
            return
            
        file_path = os.path.abspath(file_path)
        updated = False
        for r in self.app._records:
            if r.get("bid_no") == bid_no:
                r["pdf_path"] = file_path
                updated = True
                break
                
        if updated:
            db.upsert_tender_field(bid_no, "pdf_path", file_path)
            self.app._log("ok", f"Linked PDF to {bid_no}: {os.path.basename(file_path)}")
            self.on_treeview_select(None)

    def unlink_associated_pdf(self):
        sel = self.tv.selection()
        if not sel:
            return
        bid_no = self.tv.set(sel[0], "bid_no")
        if not bid_no:
            return
            
        updated = False
        for r in self.app._records:
            if r.get("bid_no") == bid_no:
                r["pdf_path"] = ""
                updated = True
                break
                
        if updated:
            db.upsert_tender_field(bid_no, "pdf_path", "")
            self.app._log("info", f"Unlinked PDF for {bid_no}")
            self.on_treeview_select(None)

    def open_associated_pdf(self):
        sel = self.tv.selection()
        if not sel:
            return
        bid_no = self.tv.set(sel[0], "bid_no")
        if not bid_no:
            return
            
        rec = None
        for r in self.app._records:
            if r.get("bid_no") == bid_no:
                rec = r
                break
        if not rec:
            return
            
        pdf_path = rec.get("pdf_path")
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showerror("File Error", f"Associated PDF file not found or not linked.\nPath: {pdf_path}")
            return
            
        import sys
        import subprocess
        import webbrowser
        try:
            if sys.platform == "win32":
                os.startfile(pdf_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", pdf_path])
            else:
                subprocess.run(["xdg-open", pdf_path])
            self.app._log("ok", f"Opened PDF for {bid_no}")
        except Exception as e:
            try:
                webbrowser.open(f"file:///{os.path.abspath(pdf_path)}")
                self.app._log("ok", f"Opened PDF for {bid_no} in browser")
            except Exception as ex:
                self.app._log("err", f"Failed to open PDF: {e}")
                messagebox.showerror("Open Error", f"Could not open PDF file:\n{e}")

    def apply_column_visibility(self):
        settings = db.load_settings()
        visible = settings.get("visible_columns")
        if not visible or not isinstance(visible, list):
            visible = [c[0] for c in TV_COLS]
        
        valid_cols = [c[0] for c in TV_COLS]
        visible = [col for col in visible if col in valid_cols]
        if not visible:
            visible = valid_cols
            
        self.tv.configure(displaycolumns=visible)

    def show_column_selector(self):
        win = tk.Toplevel(self.app)
        win.title("Select Columns")
        win.geometry("400x520")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.transient(self.app)
        win.grab_set()
        
        x = self.app.winfo_x() + (self.app.winfo_width() - 400) // 2
        y = self.app.winfo_y() + (self.app.winfo_height() - 520) // 2
        win.geometry(f"+{max(0, x)}+{max(0, y)}")

        tk.Label(win, text="Manage Columns & Ordering", font=FT, bg=BG, fg=TEXT).pack(pady=(12, 10))
        
        list_frame = tk.Frame(win, bg=PANEL, highlightthickness=1, highlightbackground="#30363D")
        list_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        canvas = tk.Canvas(list_frame, bg=PANEL, highlightthickness=0)
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scroll_content = tk.Frame(canvas, bg=PANEL)
        
        scroll_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_content, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        settings = db.load_settings()
        visible = settings.get("visible_columns")
        if not visible or not isinstance(visible, list):
            visible = [c[0] for c in TV_COLS]
            
        all_cols_ids = [c[0] for c in TV_COLS]
        current_order = []
        for vcol in visible:
            if vcol in all_cols_ids:
                current_order.append(vcol)
        for col_id in all_cols_ids:
            if col_id not in current_order:
                current_order.append(col_id)
                
        col_names = {c[0]: c[1] for c in TV_COLS}
        
        items = []
        for cid in current_order:
            var = tk.BooleanVar(value=(cid in visible))
            items.append({
                "id": cid,
                "name": col_names[cid],
                "var": var
            })
            
        def draw_list():
            for child in scroll_content.winfo_children():
                child.destroy()
                
            for idx, item in enumerate(items):
                row_fr = tk.Frame(scroll_content, bg=PANEL)
                row_fr.pack(fill="x", padx=10, pady=2, anchor="w")
                
                cb = tk.Checkbutton(
                    row_fr, text=item["name"], variable=item["var"],
                    bg=PANEL, fg=TEXT, selectcolor=BG,
                    activebackground=PANEL, activeforeground=TEXT,
                    font=FL, relief="flat", anchor="w"
                )
                cb.pack(side="left", fill="x", expand=True)
                
                btn_fr = tk.Frame(row_fr, bg=PANEL)
                btn_fr.pack(side="right", padx=5)
                
                up_btn = tk.Button(
                    btn_fr, text="▲", font=("Arial", 8), bg=CARD, fg=TEXT, relief="flat", bd=0, padx=4, pady=1,
                    command=lambda i=idx: move_up(i)
                )
                up_btn.pack(side="left", padx=2)
                if idx == 0:
                    up_btn.configure(state="disabled", fg=MUTED)
                    
                down_btn = tk.Button(
                    btn_fr, text="▼", font=("Arial", 8), bg=CARD, fg=TEXT, relief="flat", bd=0, padx=4, pady=1,
                    command=lambda i=idx: move_down(i)
                )
                down_btn.pack(side="left", padx=2)
                if idx == len(items) - 1:
                    down_btn.configure(state="disabled", fg=MUTED)
                    
        def move_up(index):
            if index > 0:
                items[index], items[index - 1] = items[index - 1], items[index]
                draw_list()
                
        def move_down(index):
            if index < len(items) - 1:
                items[index], items[index + 1] = items[index + 1], items[index]
                draw_list()
                
        draw_list()
        
        def save_columns():
            new_visible = [item["id"] for item in items if item["var"].get()]
            if not new_visible:
                new_visible = ["bid_no"]
                items[0]["var"].set(True)
                messagebox.showwarning("Selection Warning", "At least one column must be visible.", parent=win)
                return
                
            db.save_setting("visible_columns", new_visible)
            self.apply_column_visibility()
            win.destroy()
            
        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(fill="x", pady=15)
        
        self.app._btn(btn_frame, "  Apply  ", save_columns, bg=ACCENT2).pack(side="left", padx=(40, 10), expand=True, fill="x")
        self.app._btn(btn_frame, "  Cancel  ", win.destroy, bg=CARD).pack(side="right", padx=(10, 40), expand=True, fill="x")

    def start_filing_process(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showwarning("Selection Required", "Please select a tender from the table first.")
            return
        
        if len(sel) > 1:
            messagebox.showwarning("Single Selection", "Please select only one tender for filing process.")
            return
        
        iid = sel[0]
        bid_no = self.tv.set(iid, "bid_no")
        if not bid_no:
            messagebox.showwarning("Invalid Tender", "Selected row has no bid number.")
            return
        
        tender_record = None
        for r in self.app._records:
            if r.get("bid_no") == bid_no:
                tender_record = r
                break
        
        if not tender_record:
            messagebox.showerror("Error", "Tender record not found in database.")
            return
        
        # Ensure end date is present and parseable. If not, prompt the user.
        from tkinter import simpledialog
        from datetime import datetime
        
        end_date = tender_record.get('end_date', '').strip()
        parsed_date = None
        if end_date:
            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y %I:%M %p", "%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                try:
                    parsed_date = datetime.strptime(end_date, fmt)
                    break
                except ValueError:
                    pass
            if not parsed_date and len(end_date) >= 10:
                for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
                    try:
                        parsed_date = datetime.strptime(end_date[:10], fmt)
                        break
                    except ValueError:
                        pass
        
        if not parsed_date:
            user_date = simpledialog.askstring(
                "End Date Required",
                f"The tender '{bid_no}' has no valid end date.\n"
                f"Please enter the tender end date (e.g., 14/07/2026 or 14-07-2026):",
                parent=self.app
            )
            if not user_date:
                # User cancelled the prompt, abort filing
                return
            
            user_date = user_date.strip()
            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
                try:
                    parsed_date = datetime.strptime(user_date, fmt)
                    break
                except ValueError:
                    pass
            
            if not parsed_date:
                messagebox.showerror("Invalid Date", "Could not parse the date you entered. Process cancelled.")
                return
            
            # Save the date in the format they typed, and update the DB so it persists
            tender_record['end_date'] = user_date
            db.upsert_tender(tender_record)
            self.refresh_table_view()
        
        # Custom confirmation dialog with firm association dropdown
        dlg = tk.Toplevel(self.app)
        dlg.title("Start Filing Process")
        dlg.resizable(False, False)
        dlg.configure(bg=BG)
        dlg.transient(self.app)
        dlg.grab_set()
        
        # Center, position, and size dialog
        x = self.app.winfo_x() + (self.app.winfo_width() - 1100) // 2
        y = self.app.winfo_y() + (self.app.winfo_height() - 1200) // 2
        dlg.geometry(f"1100x1200+{max(0, x)}+{max(0, y)}")
        
        tk.Label(dlg, text="📁 Start Filing Process", font=("Segoe UI", 12, "bold"), bg=BG, fg=TEXT).pack(pady=(16, 12))
        
        details_fr = tk.Frame(dlg, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=15, pady=12)
        details_fr.pack(fill="x", padx=20, pady=5)
        details_fr.columnconfigure(1, weight=1)
        
        def add_detail(row_idx, label, val):
            tk.Label(details_fr, text=label, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED, anchor="w").grid(row=row_idx, column=0, sticky="w", pady=3, padx=(0, 15))
            tk.Label(details_fr, text=val, font=("Segoe UI", 9), bg=PANEL, fg=TEXTSUB, anchor="w", justify="left").grid(row=row_idx, column=1, sticky="w", pady=3)
            
        add_detail(0, "Bid No:", bid_no)
        items_txt = tender_record.get('items', 'N/A')
        if len(items_txt) > 50:
            items_txt = items_txt[:47] + "..."
        add_detail(1, "Items:", items_txt)
        dept_txt = tender_record.get('dept', 'N/A')
        if len(dept_txt) > 50:
            dept_txt = dept_txt[:47] + "..."
        add_detail(2, "Department:", dept_txt)
        
        firm_fr = tk.Frame(dlg, bg=BG)
        firm_fr.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(firm_fr, text="Associate with Firm:", font=("Segoe UI", 9, "bold"), bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 4))
        
        settings = db.load_settings()
        firms = settings.get("firms", [])
        firm_names = []
        for f in firms:
            fn = f.get("name", "").strip() if isinstance(f, dict) else str(f).strip()
            if fn and fn not in firm_names:
                firm_names.append(fn)
        firm_options = ["Auto-detect matching firm"] + firm_names

        default_firm = tender_record.get("matched_firm", "")
        if default_firm and default_firm in firm_names:
            selected_option = default_firm
        else:
            selected_option = "Auto-detect matching firm"
            
        firm_var = tk.StringVar(value=selected_option)
        firm_combo = ttk.Combobox(firm_fr, textvariable=firm_var, values=firm_options, state="readonly", font=FL)
        firm_combo.pack(fill="x", ipady=2)
        
        # Category selection
        cat_fr = tk.Frame(dlg, bg=BG)
        cat_fr.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(cat_fr, text="Select Category:", font=("Segoe UI", 9, "bold"), bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 4))
        
        category_mappings = settings.get("category_mappings") or []
        category_options = sorted({m["name"] for m in category_mappings if m.get("name")})
        current_category = tender_record.get("category", "")
        
        if current_category and current_category in category_options:
            selected_category = current_category
        elif category_options:
            selected_category = category_options[0]
        else:
            selected_category = "General"
        
        category_var = tk.StringVar(value=selected_category)
        category_combo = ttk.Combobox(cat_fr, textvariable=category_var, values=category_options, state="readonly", font=FL)
        category_combo.pack(fill="x", ipady=2)
        
        actions_fr = tk.Frame(dlg, bg=BG)
        actions_fr.pack(fill="x", padx=20, pady=5)
        tk.Label(actions_fr, text="This will:\n1. Download/verify tender PDF\n2. Extract required documents from PDF\n3. Copy matching firm documents to output folder", 
                 font=("Segoe UI", 8), bg=BG, fg=MUTED, justify="left", anchor="w").pack(fill="x")

        btn_fr = tk.Frame(dlg, bg=BG)
        btn_fr.pack(fill="x", side="bottom", pady=20, padx=20)
        
        result_holder = {"confirmed": False, "firm_name": None, "category": None}
        
        def on_start():
            result_holder["confirmed"] = True
            opt = firm_var.get()
            if opt != "Auto-detect matching firm":
                result_holder["firm_name"] = opt
            result_holder["category"] = category_var.get()
            dlg.destroy()
            
        self.app._btn(btn_fr, "  Start Process  ", on_start, bg=ACCENT).pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.app._btn(btn_fr, "  Cancel  ", dlg.destroy, bg=CARD).pack(side="right", fill="x", expand=True, padx=(6, 0))
        
        dlg.wait_window()
        
        if not result_holder["confirmed"]:
            return
            
        firm_name = result_holder["firm_name"]
        selected_category = result_holder["category"]
        
        # Persist selected category to the database
        if selected_category:
            tender_record["category"] = selected_category
            db.upsert_tender_field(bid_no, "category", selected_category)
            self.refresh_table_view()
        
        from dialogs.loading_dialog import LoadingDialog
        
        def _on_filing_done(result, exception):
            if exception:
                messagebox.showerror("Filing Error", f"Filing process failed:\n{str(exception)}", parent=self.app)
            elif result:
                self.show_filing_result(result)

        # Use a list cell so run_filing_task can reference loading_dlg before it is bound
        dlg_ref = [None]
        
        def run_filing_task(progress_cb=None):
            def dialog_log(level, message, details=None):
                self.app._log(level, message, details)
                dlg = dlg_ref[0]
                if dlg and dlg.winfo_exists():
                    dlg.append_checklist_item(level, message)
            workflow = filing_workflow.FilingWorkflow(log_fn=dialog_log, progress_cb=progress_cb)
            return workflow.start_filing_process(tender_record, firm_name=firm_name, category=selected_category)

        loading_dlg = LoadingDialog(
            self.app,
            title="Processing Filing",
            message=f"Running filing process for {bid_no}...\n(Downloading PDF, extracting required docs, copying firm files)",
            task_fn=run_filing_task,
            on_done=_on_filing_done,
            steps=[
                "Initialize filing process",
                "Download & verify tender PDF",
                "Setup folders & copy tender PDF",
                "Scan PDF for embedded links",
                "Extract & parse document text",
                "Identify tender item category",
                "Analyze required document list",
                "Extract EMD & security requirements",
                "Match required docs with firm records",
                "Copy & validate matched documents",
                "Generate reports & complete filing"
            ]
        )
        dlg_ref[0] = loading_dlg

    def show_filing_result(self, result):
        if not result.get('success'):
            messagebox.showerror("Filing Failed", f"Filing process failed:\n{result.get('error', 'Unknown error')}", parent=self.app)
            return
        
        folder_path = result.get('filing_folder', '')
        required = result.get('required_count', 0)
        matched = result.get('matched_count', 0)
        missing = result.get('missing_count', 0)
        missing_docs = result.get('missing_category_docs', [])
        
        result_dialog = tk.Toplevel(self.app)
        result_dialog.title("Filing Complete")
        result_dialog.resizable(True, True)
        result_dialog.configure(bg=BG)
        result_dialog.transient(self.app)
        result_dialog.grab_set()
        
        # Center, position, and size result dialog (larger to accommodate missing docs section)
        w, h = 800, 700
        x = self.app.winfo_x() + (self.app.winfo_width() - w) // 2
        y = self.app.winfo_y() + (self.app.winfo_height() - h) // 2
        result_dialog.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        
        # Scrollable content
        canvas = tk.Canvas(result_dialog, bg=BG)
        scrollbar = ttk.Scrollbar(result_dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(canvas_window, width=e.width)
        )
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Title
        title_lbl = tk.Label(scrollable_frame, text="✅ Filing Process Complete", font=("Segoe UI", 14, "bold"), bg=BG, fg=SUCCESS)
        title_lbl.pack(pady=20)
        
        # Summary section
        summary_frame = tk.Frame(scrollable_frame, bg=PANEL, padx=15, pady=15)
        summary_frame.pack(fill="x", padx=20, pady=10)
        
        tk.Label(summary_frame, text="Filing Folder:", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).grid(row=0, column=0, sticky="w", pady=5)
        tk.Label(summary_frame, text=folder_path, font=("Segoe UI", 9), bg=PANEL, fg=TEXTSUB, wraplength=550, justify="left").grid(row=0, column=1, sticky="w", pady=5, padx=(10, 0))
        
        tk.Label(summary_frame, text="Document Status:", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).grid(row=1, column=0, sticky="w", pady=5)
        status_text = f"Required: {required} | Matched: {matched} | Missing: {missing}"
        tk.Label(summary_frame, text=status_text, font=("Segoe UI", 9), bg=PANEL, fg=TEXTSUB).grid(row=1, column=1, sticky="w", pady=5, padx=(10, 0))
        
        # Missing documents section
        if missing > 0 and missing_docs:
            tk.Label(scrollable_frame, text="⚠️ Missing Documents", font=("Segoe UI", 12, "bold"), bg=BG, fg=WARN).pack(pady=(20, 10))
            
            missing_frame = tk.Frame(scrollable_frame, bg=PANEL, padx=15, pady=15)
            missing_frame.pack(fill="x", padx=20, pady=10)
            
            for i, doc in enumerate(missing_docs):
                doc_row = tk.Frame(missing_frame, bg=PANEL)
                doc_row.pack(fill="x", pady=5)
                
                doc_name = doc.get('name', 'Unknown')
                tk.Label(doc_row, text=f"• {doc_name}", font=("Segoe UI", 9), bg=PANEL, fg=TEXTSUB).pack(side="left")
                
                # Browse and link button for each missing document
                def make_link_button(doc_info=doc):
                    def browse_and_link():
                        from tkinter import filedialog
                        file_paths = filedialog.askopenfilenames(
                            title=f"Select file(s) for {doc_info.get('name', 'document')}",
                            filetypes=[("All Files", "*.*"), ("PDF Files", "*.pdf"), ("Documents", "*.doc;*.docx")]
                        )
                        if file_paths:
                            # Copy files to filing folder
                            import shutil
                            linked_count = 0
                            errors = []
                            for file_path in file_paths:
                                try:
                                    filename = os.path.basename(file_path)
                                    # Handle duplicate filenames
                                    counter = 1
                                    dest_path = os.path.join(folder_path, filename)
                                    while os.path.exists(dest_path):
                                        name, ext = os.path.splitext(filename)
                                        dest_path = os.path.join(folder_path, f"{name}_{counter}{ext}")
                                        counter += 1
                                    
                                    shutil.copy2(file_path, dest_path)
                                    linked_count += 1
                                except Exception as e:
                                    errors.append(f"{os.path.basename(file_path)}: {str(e)}")
                            
                            if linked_count > 0:
                                msg = f"Successfully linked {linked_count} file(s):\n\n"
                                for file_path in file_paths:
                                    if not any(os.path.basename(file_path) in err for err in errors):
                                        msg += f"✓ {os.path.basename(file_path)}\n"
                                if errors:
                                    msg += f"\nFailed to link:\n" + "\n".join(errors)
                                messagebox.showinfo("Success", msg, parent=result_dialog)
                                # Update the button to show linked status
                                link_btn.config(text=f"✅ Linked ({linked_count})", bg=SUCCESS, state="disabled")
                            else:
                                messagebox.showerror("Error", f"Failed to link any files:\n" + "\n".join(errors), parent=result_dialog)
                    
                    link_btn = tk.Button(doc_row, text="📎 Link File(s)", command=browse_and_link,
                                        bg=CARD, fg=TEXT, relief="flat", font=("Segoe UI", 8),
                                        padx=8, pady=2, cursor="hand2")
                    link_btn.pack(side="right")
                    return link_btn
                
                link_btn = make_link_button(doc)
        
        # Files generated section
        tk.Label(scrollable_frame, text="📄 Files Generated", font=("Segoe UI", 12, "bold"), bg=BG, fg=TEXT).pack(pady=(20, 10))
        
        files_frame = tk.Frame(scrollable_frame, bg=PANEL, padx=15, pady=15)
        files_frame.pack(fill="x", padx=20, pady=10)
        
        tk.Label(files_frame, text="• Document_Checklist.txt", font=("Segoe UI", 9), bg=PANEL, fg=TEXTSUB).pack(anchor="w", pady=3)
        tk.Label(files_frame, text="• Filing_Summary.txt", font=("Segoe UI", 9), bg=PANEL, fg=TEXTSUB).pack(anchor="w", pady=3)
        
        # GEM Portal Document Requirements section
        tk.Label(scrollable_frame, text="🌐 GEM Portal Document Requirements", font=("Segoe UI", 12, "bold"), bg=BG, fg=ACCENT).pack(pady=(20, 10))
        
        gem_frame = tk.Frame(scrollable_frame, bg=PANEL, padx=15, pady=15)
        gem_frame.pack(fill="x", padx=20, pady=10)
        
        # Get dynamic GeM requirements from result
        raw_gem_reqs = result.get('gem_requirements', [])
        if not raw_gem_reqs:
            # Fallback to defaults
            raw_gem_reqs = [
                "Experience Criteria",
                "Past Performance",
                "Bidder Turnover",
                "Additional Doc 1 (Requested in ATC)",
                "Additional Doc 2 (Requested in ATC)",
                "Certificate (Requested in ATC)",
                "Compliance of BoQ specification",
                "Financial document",
            ]
            
        gem_requirements = []
        for req_name in raw_gem_reqs:
            is_required = True
            # In GeM, "Certificate (Requested in ATC)" is optional/not strictly marked with asterisk
            if "Certificate (Requested in ATC)" in req_name or "Certificate (requested in ATC)" in req_name:
                is_required = False
                
            clean_name = req_name.replace("*", "").strip()
            gem_requirements.append({
                "name": clean_name + ("*" if is_required else ""),
                "required": is_required,
                "max_size": "10MB",
                "max_pages": 100,
                "note": "Merge all ATC docs into single file" if "Certificate (Requested in ATC)" in clean_name else None
            })
        
        gem_mappings = {}  # Store mappings for saving
        
        for i, req in enumerate(gem_requirements):
            req_row = tk.Frame(gem_frame, bg=PANEL)
            req_row.pack(fill="x", pady=8)
            
            # Requirement name with asterisk for required
            name_text = req["name"]
            label_color = TEXTSUB
            if req.get("required"):
                label_color = ERR
            tk.Label(req_row, text=name_text, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=label_color).pack(anchor="w")
            
            # Note if present
            if req.get("note"):
                tk.Label(req_row, text=f"Note: {req['note']}", font=("Segoe UI", 8), bg=PANEL, fg=MUTED).pack(anchor="w")
            
            # Constraints
            constraints = f"Max: {req['max_size']}, {req['max_pages']} pages"
            tk.Label(req_row, text=constraints, font=("Segoe UI", 8), bg=PANEL, fg=MUTED).pack(anchor="w")
            
            # File linking button
            def make_gem_link_button(req_info=req, idx=i):
                def browse_and_link():
                    from tkinter import filedialog
                    file_paths = filedialog.askopenfilenames(
                        title=f"Select file(s) for {req_info['name']}",
                        filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
                    )
                    if file_paths:
                        import shutil
                        linked_count = 0
                        errors = []
                        linked_files = []
                        for file_path in file_paths:
                            try:
                                filename = os.path.basename(file_path)
                                # Handle duplicate filenames
                                counter = 1
                                dest_path = os.path.join(folder_path, filename)
                                while os.path.exists(dest_path):
                                    name, ext = os.path.splitext(filename)
                                    dest_path = os.path.join(folder_path, f"{name}_{counter}{ext}")
                                    counter += 1
                                
                                shutil.copy2(file_path, dest_path)
                                linked_count += 1
                                linked_files.append(filename)
                            except Exception as e:
                                errors.append(f"{os.path.basename(file_path)}: {str(e)}")
                        
                        if linked_count > 0:
                            gem_mappings[idx] = linked_files
                            msg = f"Successfully linked {linked_count} file(s):\n\n"
                            for fname in linked_files:
                                msg += f"✓ {fname}\n"
                            if errors:
                                msg += f"\nFailed to link:\n" + "\n".join(errors)
                            messagebox.showinfo("Success", msg, parent=result_dialog)
                            gem_link_btn.config(text=f"✅ Linked ({linked_count})", bg=SUCCESS, state="disabled")
                        else:
                            messagebox.showerror("Error", f"Failed to link any files:\n" + "\n".join(errors), parent=result_dialog)
                
                gem_link_btn = tk.Button(req_row, text="📎 Link File(s)", command=browse_and_link,
                                         bg=CARD, fg=TEXT, relief="flat", font=("Segoe UI", 8),
                                         padx=8, pady=2, cursor="hand2")
                gem_link_btn.pack(side="right", pady=5)
                return gem_link_btn
            
            gem_link_btn = make_gem_link_button(req)
        
        # GSTIN Selection
        gstin_frame = tk.Frame(gem_frame, bg=PANEL)
        gstin_frame.pack(fill="x", pady=15)
        
        tk.Label(gstin_frame, text="GSTIN for Annual Milestone Charges*", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=ERR).pack(anchor="w")
        
        # Load firm GSTINs from settings
        settings = db.load_settings()
        firms = settings.get('firms', [])
        gstin_options = []
        if firms:
            for firm in firms:
                gstin = firm.get('gstin', '')
                if gstin:
                    gstin_options.append(gstin)
        
        if not gstin_options:
            gstin_options = ["No GSTIN configured"]
        
        gstin_var = tk.StringVar(value=gstin_options[0] if gstin_options else "")
        gstin_combo = ttk.Combobox(gstin_frame, textvariable=gstin_var, values=gstin_options,
                                    state="readonly", font=FL, width=40)
        gstin_combo.pack(pady=5)
        
        # Address Selection
        address_frame = tk.Frame(gem_frame, bg=PANEL)
        address_frame.pack(fill="x", pady=15)
        
        tk.Label(address_frame, text="Address for Annual Milestone Charge/Transaction Charge Invoice*", 
                font=("Segoe UI", 9, "bold"), bg=PANEL, fg=ERR).pack(anchor="w")
        
        # Load firm addresses from settings
        address_options = []
        if firms:
            for firm in firms:
                address = firm.get('address', '')
                if address:
                    address_options.append(address)
        
        if not address_options:
            address_options = ["No address configured"]
        
        address_var = tk.StringVar(value=address_options[0] if address_options else "")
        address_combo = ttk.Combobox(address_frame, textvariable=address_var, values=address_options,
                                     state="readonly", font=FL, width=40)
        address_combo.pack(pady=5)
        
        # MSE Manufacturing Question
        mse_frame = tk.Frame(gem_frame, bg=PANEL)
        mse_frame.pack(fill="x", pady=15)
        
        tk.Label(mse_frame, text="Are you manufacturing MSE for this product?*", 
                font=("Segoe UI", 9, "bold"), bg=PANEL, fg=ERR).pack(anchor="w")
        
        mse_var = tk.StringVar(value="No")
        mse_frame_radio = tk.Frame(mse_frame, bg=PANEL)
        mse_frame_radio.pack(pady=5)
        
        tk.Radiobutton(mse_frame_radio, text="Yes", variable=mse_var, value="Yes",
                      bg=PANEL, fg=TEXT, font=FL).pack(side="left", padx=10)
        tk.Radiobutton(mse_frame_radio, text="No", variable=mse_var, value="No",
                      bg=PANEL, fg=TEXT, font=FL).pack(side="left", padx=10)
        
        # Save GEM mappings button
        def save_gem_mappings():
            gem_data = {
                "gstin": gstin_var.get(),
                "address": address_var.get(),
                "mse_manufacturing": mse_var.get(),
                "document_mappings": gem_mappings
            }
            
            # Save to filing summary
            try:
                summary_file = os.path.join(folder_path, "GEM_Requirements_Mapping.txt")
                with open(summary_file, 'w', encoding='utf-8') as f:
                    f.write("GEM Portal Document Requirements Mapping\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(f"Tender: {result.get('tender_record', {}).get('bid_no', 'N/A')}\n")
                    f.write(f"Filing Folder: {folder_path}\n\n")
                    
                    f.write("GSTIN: " + gem_data["gstin"] + "\n")
                    f.write("Address: " + gem_data["address"] + "\n")
                    f.write("MSE Manufacturing: " + gem_data["mse_manufacturing"] + "\n\n")
                    
                    f.write("Document Mappings:\n")
                    for idx, files in gem_data["document_mappings"].items():
                        req_name = gem_requirements[idx]["name"]
                        f.write(f"\n{req_name}:\n")
                        for file in files:
                            f.write(f"  - {file}\n")
                
                messagebox.showinfo("Saved", f"GEM requirements mapping saved to:\n{summary_file}", parent=result_dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save GEM mapping: {e}", parent=result_dialog)
        
        save_gem_btn = self.app._btn(gem_frame, "💾 Save GEM Requirements Mapping", save_gem_mappings, bg=ACCENT2)
        save_gem_btn.pack(pady=15)
        
        # Action buttons
        btn_frame = tk.Frame(scrollable_frame, bg=BG)
        btn_frame.pack(pady=20)
        
        def open_folder():
            try:
                os.startfile(folder_path)
            except Exception:
                import subprocess
                try:
                    subprocess.Popen(["xdg-open", folder_path])
                except Exception:
                    pass
        
        self.app._btn(btn_frame, "📁 Open Folder", open_folder, bg=ACCENT).pack(side="left", padx=5)
        self.app._btn(btn_frame, "📋 Copy Path", lambda: self.app._copy_to_clipboard(folder_path), bg=CARD).pack(side="left", padx=5)
        self.app._btn(btn_frame, "Close", result_dialog.destroy, bg=CARD).pack(side="left", padx=5)

    def open_tender_url(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showwarning("Selection Required", "Please select a tender from the table first.")
            return
        
        bid_url = self.tv.set(sel[0], "bid_url")
        if bid_url:
            import webbrowser
            webbrowser.open(bid_url)
        else:
            messagebox.showinfo("No URL", "This tender has no associated URL.")

    def copy_bid_number(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showwarning("Selection Required", "Please select a tender from the table first.")
            return
        
        bid_no = self.tv.set(sel[0], "bid_no")
        if bid_no:
            self.app._copy_to_clipboard(bid_no)
            self.app._log("ok", f"Copied bid number: {bid_no}")

    def do_fetch_sel(self):
        self.app._do_fetch_sel()

    def sel_all(self):
        self.tv.selection_set(self.tv.get_children())

    def del_sel(self):
        sel = self.tv.selection()
        if not sel: return
        
        bids_to_del = []
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                bids_to_del.append(bid_no)
                
        self.app._records = [r for r in self.app._records if r.get("bid_no") not in bids_to_del]
        
        self.refresh_table_view()
        self.app._log("info", f"Deleted {len(sel)} row(s).")
        db.save_all_tenders(self.app._records)
        try:
            if self.app.notebook.index(self.app.notebook.select()) == self.app.notebook.index(self.app.tab_calendar):
                self.app._update_calendar()
                self.app._update_details()
        except:
            pass

    def save_selected(self):
        sel = self.tv.selection()
        if not sel:
            self.app._log("warn", "No rows selected."); return
        folder = self.app.save_folder.get().strip()
        if not folder:
            self.app._set_status("Set output folder first.", ERR); return
        os.makedirs(folder, exist_ok=True)
        fy   = financial_year(datetime.now())
        pat  = db.load_settings().get("excel_filename_pattern", "GEM_Tenders_FY_{fy}")
        path = xl_path(folder, fy, pattern=pat)
        ensure_workbook(path)
        
        recs = []
        bids_saved = []
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self.app._records:
                    if r.get("bid_no") == bid_no:
                        recs.append(r)
                        bids_saved.append(bid_no)
                        break
        try:
            snos = xl_append(path, recs)
            msg = f"Saved {len(snos)} row(s) → {os.path.basename(path)}  (S.No {snos[0]}–{snos[-1]})"
            self.app._log("ok", msg)
            self.app._set_status(msg, SUCCESS)
            self.app._fy_tick()
            
            for iid in sel: 
                self.tv.item(iid, tags=("saved",))
                
            for r in self.app._records:
                if r.get("bid_no") in bids_saved:
                    r["is_saved"] = True
                    
            db.save_all_tenders(self.app._records)
        except Exception as ex:
            self.app._log("err", f"Save error: {ex}")
            messagebox.showerror("Save Error", str(ex))

    def show_tags_dialog(self):
        self.app._show_tags_dialog()

    def show_comments_dialog(self):
        self.app._show_comments_dialog()
