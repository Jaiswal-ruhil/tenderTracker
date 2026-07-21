# -*- coding: utf-8 -*-
"""
firms_dialog.py
~~~~~~~~~~~~~~~
Modern Firm Management Modal Dialog for TenderTracker.
Features include:
- Searchable firm list cards with doc completion badges
- Product category chips with live tender match estimation
- Compliance document tracking (GST, PAN, MSME, ITR, Balance Sheets, Turnover)
- 📁 One-click Auto-Scan Folder tool to automatically discover compliance PDFs
- Real-time MongoDB sync and immediate tender re-evaluation
"""

import os
import re
from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Local imports
from config import BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, ERR, SUCCESS, WARN, FL
import db
from .loading_dialog import LoadingDialog


class FirmsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grab_set()
        self.transient(parent)
        self.title("Manage Firms & Document Vault")
        self.configure(bg=BG)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        init_w = min(1220, max(840, screen_w - 40))
        init_h = min(860, max(560, screen_h - 60))
        self.minsize(800, 540)

        x = parent.winfo_x() + (parent.winfo_width() - init_w) // 2
        y = parent.winfo_y() + (parent.winfo_height() - init_h) // 2
        self.geometry(f"{init_w}x{init_h}+{max(0, x)}+{max(0, y)}")

        # Accent colors
        DOC_UPLOADED   = "#2EA043"
        DOC_EXPIRING   = "#D29922"
        DOC_EXPIRED    = "#F85149"
        DOC_MISSING    = "#D29922"
        DOC_NONE       = "#484F58"
        ROW_ALT        = "#1C2128"
        SECTION_LINE   = "#30363D"
        CHIP_BG        = "#1C3557"
        CHIP_FG        = "#79C0FF"
        UPLOAD_BG      = "#1C3557"

        def normalize_multi_value(value):
            if isinstance(value, list):
                raw_items = value
            else:
                raw_items = str(value or "").split(",")
            items = []
            for item in raw_items:
                cleaned = str(item).strip()
                if cleaned and cleaned not in items:
                    items.append(cleaned)
            return items

        def display_multi_value(value):
            return ", ".join(normalize_multi_value(value))

        def _check_doc_status(path: str, expiry_str: str) -> tuple:
            """Check (status_code, status_text, color) for a document."""
            if not path or not path.strip():
                return ("NONE", "Not uploaded", DOC_NONE)
            if not os.path.exists(path.strip()):
                return ("MISSING", "File missing", DOC_MISSING)

            if expiry_str and expiry_str.strip():
                clean_exp = expiry_str.strip().replace('/', '-')
                dt = None
                for fmt in ["%Y-%m-%d", "%d-%m-%Y"]:
                    try:
                        dt = datetime.strptime(clean_exp, fmt).date()
                        break
                    except ValueError:
                        pass
                if dt:
                    today = date.today()
                    days = (dt - today).days
                    if days < 0:
                        return ("EXPIRED", f"Expired ({dt.strftime('%d %b %Y')})", DOC_EXPIRED)
                    elif days <= 30:
                        return ("EXPIRING", f"Expiring in {days}d ({dt.strftime('%d %b %Y')})", DOC_EXPIRING)
                    else:
                        return ("VALID", f"Valid (Exp: {dt.strftime('%d %b %Y')})", DOC_UPLOADED)

            return ("VALID", "Uploaded (Valid)", DOC_UPLOADED)

        # Document type definitions: (key, icon, label, optional)
        DOCUMENT_TYPES = [
            ("gst",           "📄", "GST Certificate",        False),
            ("pan",           "🪪", "PAN Card",                False),
            ("msme",          "🏭", "MSME Certificate",        True),
            ("itr_1",         "📊", "ITR – Year 1",            False),
            ("itr_2",         "📊", "ITR – Year 2",            False),
            ("itr_3",         "📊", "ITR – Year 3",            False),
            ("bs_1",          "📑", "Balance Sheet – Year 1",  False),
            ("bs_2",          "📑", "Balance Sheet – Year 2",  False),
            ("bs_3",          "📑", "Balance Sheet – Year 3",  False),
            ("turnover_cert", "📜", "Turnover Certificate",    False),
            ("shareholder",   "👥", "Shareholder Pattern",     True),
        ]
        REQUIRED_KEYS = {k for k, _, _, opt in DOCUMENT_TYPES if not opt}
        TOTAL_REQUIRED = len(REQUIRED_KEYS)

        def _doc_completion(documents: dict, expiries: dict = None) -> tuple:
            expiries = expiries or {}
            uploaded = 0
            expired_count = 0
            for k in REQUIRED_KEYS:
                p = documents.get(k, "").strip()
                if p and os.path.exists(p):
                    uploaded += 1
                    status_code, _, _ = _check_doc_status(p, expiries.get(k, ""))
                    if status_code == "EXPIRED":
                        expired_count += 1
            return uploaded, TOTAL_REQUIRED, expired_count

        # Load firms from settings with deduplication
        settings = db.load_settings()
        raw_firms = settings.get("firms", [])
        firms_list = []
        seen_names = set()
        for firm in raw_firms:
            fn = firm.get("name", "").strip()
            if not fn or fn.lower() in seen_names:
                continue
            seen_names.add(fn.lower())
            firms_list.append({
                "name": fn,
                "categories": normalize_multi_value(firm.get("categories", [])),
                "locations": firm.get("locations", ""),
                "exclude_keywords": firm.get("exclude_keywords", ""),
                "documents": firm.get("documents", {}),
                "expiries": firm.get("expiries", {}),
            })

        # ── Title Bar ────────────────────────────────────────────────────
        title_bar = tk.Frame(self, bg=PANEL, pady=10,
                             highlightthickness=1, highlightbackground=SECTION_LINE)
        title_bar.pack(fill="x", side="top")
        
        tk.Label(title_bar, text="🏢  Manage Bidding Firms", font=("Segoe UI", 13, "bold"),
                 bg=PANEL, fg=TEXT).pack(side="left", padx=16)
        
        firm_count_var = tk.StringVar(value=f"{len(firms_list)} firm(s)")
        tk.Label(title_bar, textvariable=firm_count_var,
                 font=("Segoe UI", 9, "bold"), bg=PANEL, fg=ACCENT2).pack(side="left", padx=(0, 0))

        # ── Bottom Bar ───────────────────────────────────────────────────
        bot_fr = tk.Frame(self, bg=PANEL, pady=10,
                          highlightthickness=1, highlightbackground=SECTION_LINE)
        bot_fr.pack(fill="x", side="bottom")

        # ── Main Split Container ─────────────────────────────────────────
        main_fr = tk.Frame(self, bg=BG)
        main_fr.pack(fill="both", expand=True, padx=0, pady=0)
        main_fr.columnconfigure(0, weight=0, minsize=260)
        main_fr.columnconfigure(1, weight=1)
        main_fr.rowconfigure(0, weight=1)

        # ── LEFT: Firm List Panel ────────────────────────────────────────
        left_fr = tk.Frame(main_fr, bg=PANEL,
                           highlightthickness=1, highlightbackground=SECTION_LINE)
        left_fr.grid(row=0, column=0, sticky="nsew")
        left_fr.rowconfigure(1, weight=1)
        left_fr.columnconfigure(0, weight=1)

        left_hdr = tk.Frame(left_fr, bg=PANEL, pady=8, padx=10)
        left_hdr.grid(row=0, column=0, sticky="ew")

        tk.Label(left_hdr, text="REGISTERED FIRMS", font=("Segoe UI", 8, "bold"),
                 bg=PANEL, fg=MUTED).pack(anchor="w")

        search_var = tk.StringVar()
        search_ent = tk.Entry(left_hdr, textvariable=search_var, bg=CARD, fg=TEXT,
                              insertbackground=TEXT, relief="flat", font=("Segoe UI", 9),
                              highlightthickness=1, highlightbackground=SECTION_LINE, highlightcolor=ACCENT2)
        search_ent.pack(fill="x", pady=(4, 0))
        search_ent.insert(0, "Search firm...")
        
        def _on_search_focus(e):
            if search_ent.get() == "Search firm...":
                search_ent.delete(0, "end")
        def _on_search_blur(e):
            if not search_ent.get().strip():
                search_ent.insert(0, "Search firm...")
        search_ent.bind("<FocusIn>", _on_search_focus)
        search_ent.bind("<FocusOut>", _on_search_blur)

        # Scrollable list area
        list_canvas = tk.Canvas(left_fr, bg=PANEL, highlightthickness=0)
        list_scroll = ttk.Scrollbar(left_fr, orient="vertical", command=list_canvas.yview)
        list_canvas.configure(yscrollcommand=list_scroll.set)
        list_canvas.grid(row=1, column=0, sticky="nsew")
        list_scroll.grid(row=1, column=1, sticky="ns")

        list_inner = tk.Frame(list_canvas, bg=PANEL)
        _list_win = list_canvas.create_window((0, 0), window=list_inner, anchor="nw")

        def _on_list_configure(e):
            list_canvas.configure(scrollregion=list_canvas.bbox("all"))
        def _on_list_canvas_configure(e):
            list_canvas.itemconfig(_list_win, width=e.width)
        list_inner.bind("<Configure>", _on_list_configure)
        list_canvas.bind("<Configure>", _on_list_canvas_configure)

        def _bind_list_mw(w):
            w.bind("<MouseWheel>", lambda e: list_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
            for ch in w.winfo_children():
                _bind_list_mw(ch)
        list_inner.bind("<Map>", lambda e: _bind_list_mw(list_inner))

        ttk.Separator(left_fr, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew")
        lbtn_fr = tk.Frame(left_fr, bg=PANEL, pady=8)
        lbtn_fr.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8)

        _selected_idx = [None]
        _card_frames  = []

        def _make_firm_card(idx, firm_data, selected=False):
            card_bg  = PANEL if selected else CARD
            border_c = ACCENT2 if selected else SECTION_LINE

            outer = tk.Frame(list_inner, bg=border_c, highlightthickness=0, pady=1)
            outer.pack(fill="x", padx=6, pady=3)

            inner = tk.Frame(outer, bg=card_bg if selected else CARD, padx=10, pady=8, cursor="hand2")
            inner.pack(fill="x")

            name = firm_data.get("name", "Unnamed")
            cats = firm_data.get("categories", [])
            docs = firm_data.get("documents", {})
            exps = firm_data.get("expiries", {})
            up, tot, exp_cnt = _doc_completion(docs, exps)
            cat_cnt = len(cats) if isinstance(cats, list) else len(normalize_multi_value(cats))

            name_lbl = tk.Label(inner, text=name,
                                font=("Segoe UI", 10, "bold" if selected else "normal"),
                                bg=inner.cget("bg"), fg=TEXT, anchor="w")
            name_lbl.pack(fill="x")

            meta_fr = tk.Frame(inner, bg=inner.cget("bg"))
            meta_fr.pack(fill="x", pady=(4, 0))

            cat_badge = tk.Label(meta_fr, text=f" {cat_cnt} cat ", font=("Segoe UI", 7, "bold"),
                                 bg="#238636", fg="#AFFFB0", padx=3, pady=1)
            cat_badge.pack(side="left", padx=(0, 4))

            if exp_cnt > 0:
                doc_color = DOC_EXPIRED
                doc_fg    = "#FFD2D2"
                doc_txt   = f" {up}/{tot} ({exp_cnt} Exp) "
            else:
                doc_color = DOC_UPLOADED if up == tot else (DOC_MISSING if up > 0 else CARD)
                doc_fg    = "#AFFFB0" if up == tot else ("#FFE08A" if up > 0 else MUTED)
                doc_txt   = f" {up}/{tot} docs "

            doc_badge = tk.Label(meta_fr, text=doc_txt, font=("Segoe UI", 7, "bold"),
                                 bg=doc_color, fg=doc_fg, padx=3, pady=1)
            doc_badge.pack(side="left")

            def _click(e, i=idx):
                _on_card_click(i)
            for w in [outer, inner, name_lbl, meta_fr, cat_badge, doc_badge]:
                w.bind("<Button-1>", _click)

            return outer

        def _on_card_click(idx):
            _selected_idx[0] = idx
            _refresh_cards(selected=idx)
            if 0 <= idx < len(firms_list):
                _show_form(firms_list[idx], idx=idx)

        def _refresh_cards(selected=None):
            for w in list_inner.winfo_children():
                w.destroy()
            _card_frames.clear()

            filter_text = search_var.get().strip().lower()
            if filter_text == "search firm...":
                filter_text = ""

            visible_count = 0
            for i, f in enumerate(firms_list):
                fn = f.get("name", "").lower()
                if filter_text and filter_text not in fn:
                    continue
                visible_count += 1
                card = _make_firm_card(i, f, selected=(i == selected))
                _card_frames.append(card)

            if visible_count == 0:
                tk.Label(list_inner, text="No matching firms", font=FL, bg=PANEL, fg=MUTED).pack(pady=20)

            firm_count_var.set(f"{len(firms_list)} firm(s)")

        search_var.trace_add("write", lambda *a: _refresh_cards(selected=_selected_idx[0]))

        # ── RIGHT: Form Panel ────────────────────────────────────────────
        right_fr = tk.Frame(main_fr, bg=BG)
        right_fr.grid(row=0, column=1, sticky="nsew")
        right_fr.columnconfigure(0, weight=1)
        right_fr.rowconfigure(0, weight=1)

        # Placeholder
        placeholder_fr = tk.Frame(right_fr, bg=BG)
        placeholder_fr.grid(row=0, column=0, sticky="nsew")
        placeholder_fr.rowconfigure(0, weight=1)
        placeholder_fr.columnconfigure(0, weight=1)
        
        tk.Label(placeholder_fr, text="🏢", font=("Segoe UI", 48), bg=BG, fg="#30363D").grid(row=0, column=0, pady=(60, 4))
        tk.Label(placeholder_fr, text="Select a firm from the left list\nor click  + Add Firm  to create a new one",
                 font=("Segoe UI", 11), bg=BG, fg=MUTED, justify="center").grid(row=1, column=0)

        # Scrollable Canvas for Form
        _form_canvas = tk.Canvas(right_fr, bg=BG, highlightthickness=0)
        _form_scroll = ttk.Scrollbar(right_fr, orient="vertical", command=_form_canvas.yview)
        _form_canvas.configure(yscrollcommand=_form_scroll.set)

        form_fr = tk.Frame(_form_canvas, bg=BG, padx=20, pady=12)
        _form_win = _form_canvas.create_window((0, 0), window=form_fr, anchor="nw")

        def _on_form_configure(e):
            _form_canvas.configure(scrollregion=_form_canvas.bbox("all"))
        def _on_canvas_configure(e):
            _form_canvas.itemconfig(_form_win, width=e.width)
        form_fr.bind("<Configure>", _on_form_configure)
        _form_canvas.bind("<Configure>", _on_canvas_configure)

        def _bind_mw(widget):
            widget.bind("<MouseWheel>", lambda e: _form_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
            for ch in widget.winfo_children():
                _bind_mw(ch)
        form_fr.bind("<Map>", lambda e: _bind_mw(form_fr))

        def _section_header(parent, icon, title, subtitle=None):
            fr = tk.Frame(parent, bg=BG)
            fr.pack(fill="x", pady=(16, 6))
            ttk.Separator(fr, orient="horizontal").pack(fill="x", pady=(0, 6))
            hdr = tk.Frame(fr, bg=BG)
            hdr.pack(fill="x")
            tk.Label(hdr, text=icon, font=("Segoe UI", 11), bg=BG, fg=TEXT).pack(side="left", padx=(0, 6))
            tk.Label(hdr, text=title, font=("Segoe UI", 9, "bold"), bg=BG, fg=TEXT).pack(side="left")
            if subtitle:
                tk.Label(hdr, text=subtitle, font=("Segoe UI", 8), bg=BG, fg=TEXTSUB).pack(side="left", padx=(10, 0))

        def _field(parent, label, hint=None):
            fr = tk.Frame(parent, bg=BG)
            fr.pack(fill="x", pady=(0, 10))
            lbl_fr = tk.Frame(fr, bg=BG)
            lbl_fr.pack(fill="x")
            tk.Label(lbl_fr, text=label, font=("Segoe UI", 8, "bold"), bg=BG, fg=MUTED).pack(side="left")
            if hint:
                tk.Label(lbl_fr, text=hint, font=("Segoe UI", 7), bg=BG, fg=TEXTSUB).pack(side="left", padx=(8, 0))
            var = tk.StringVar()
            ent = tk.Entry(fr, textvariable=var, bg=CARD, fg=TEXT, insertbackground=TEXT,
                           relief="flat", font=("Segoe UI", 10), highlightthickness=1,
                           highlightbackground=SECTION_LINE, highlightcolor=ACCENT2)
            ent.pack(fill="x", pady=(4, 0), ipady=6)
            return var, ent

        # ── Firm Name ──
        nm_hdr = tk.Frame(form_fr, bg=BG)
        nm_hdr.pack(fill="x", pady=(0, 4))
        tk.Label(nm_hdr, text="Firm Name", font=("Segoe UI", 8, "bold"), bg=BG, fg=MUTED).pack(side="left")
        name_var = tk.StringVar()
        name_ent = tk.Entry(form_fr, textvariable=name_var, bg=CARD, fg=TEXT, insertbackground=TEXT,
                            relief="flat", font=("Segoe UI", 12, "bold"), highlightthickness=1,
                            highlightbackground=SECTION_LINE, highlightcolor=ACCENT2)
        name_ent.pack(fill="x", pady=(0, 4), ipady=7)

        # ── Product Categories ──
        _section_header(form_fr, "🏷️", "Product Categories", "tenders are matched against these keywords")
        cat_section = tk.Frame(form_fr, bg=BG)
        cat_section.pack(fill="x", pady=(0, 4))

        cat_hdr_fr = tk.Frame(cat_section, bg=BG)
        cat_hdr_fr.pack(fill="x")
        live_match_lbl = tk.Label(cat_hdr_fr, text="", font=("Segoe UI", 8), bg=BG, fg=SUCCESS)
        live_match_lbl.pack(side="right", padx=4)

        chips_outer = tk.Frame(cat_section, bg=CARD, highlightthickness=1, highlightbackground=SECTION_LINE)
        chips_outer.pack(fill="x", pady=(4, 0))

        chips_canvas = tk.Canvas(chips_outer, bg=CARD, highlightthickness=0, height=110)
        chips_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        chips_frame = tk.Frame(chips_canvas, bg=CARD)
        chips_window = chips_canvas.create_window((0, 0), window=chips_frame, anchor="nw")
        chips_frame.bind("<Configure>", lambda e: chips_canvas.configure(scrollregion=chips_canvas.bbox("all")))
        chips_canvas.bind("<Configure>", lambda e: chips_canvas.itemconfig(chips_window, width=e.width))

        current_categories = []

        def _update_live_count():
            try:
                cats = [c.lower() for c in current_categories if c]
                if not cats:
                    live_match_lbl.configure(text="")
                    return
                count = sum(
                    1 for r in getattr(self.parent, '_records', [])
                    if any(kw in " ".join([
                        str(r.get("items", "")), str(r.get("category", "")),
                        str(r.get("dept", "")), str(r.get("bid_no", ""))
                    ]).lower() for kw in cats)
                )
                live_match_lbl.configure(
                    text=f"~{count} tender{'s' if count != 1 else ''} matched",
                    fg=SUCCESS if count > 0 else MUTED
                )
            except Exception:
                live_match_lbl.configure(text="")

        def _rebuild_chips():
            for w in chips_frame.winfo_children():
                w.destroy()
            col = 0
            row_fr = None
            MAX_COLS = 5
            for i, cat in enumerate(current_categories):
                if col % MAX_COLS == 0:
                    row_fr = tk.Frame(chips_frame, bg=CARD)
                    row_fr.pack(anchor="w", pady=2, padx=4)
                    col = 0
                chip = tk.Frame(row_fr, bg=CHIP_BG, highlightthickness=1, highlightbackground=ACCENT2)
                chip.pack(side="left", padx=(0, 6), pady=1)
                tk.Label(chip, text=cat, font=("Segoe UI", 9), bg=CHIP_BG, fg=CHIP_FG, padx=6, pady=3).pack(side="left")
                
                def _make_rm(idx=i):
                    def _rm():
                        current_categories.pop(idx)
                        _rebuild_chips()
                        _update_live_count()
                    return _rm
                    
                tk.Button(chip, text="×", command=_make_rm(), bg=CHIP_BG, fg=ERR, relief="flat",
                          font=("Segoe UI", 9, "bold"), padx=4, pady=2, activebackground="#2D2D2D",
                          cursor="hand2", bd=0).pack(side="right")
                col += 1

            if not current_categories:
                tk.Label(chips_frame, text="No categories yet — add below", font=FL, bg=CARD, fg=MUTED).pack(padx=8, pady=12)

            chips_frame.update_idletasks()
            chips_canvas.configure(scrollregion=chips_canvas.bbox("all"))

        add_row = tk.Frame(cat_section, bg=BG)
        add_row.pack(fill="x", pady=(8, 0))

        settings_now = db.load_settings()
        mappings_now = settings_now.get("category_mappings") or []
        known_cats = sorted({m["name"] for m in mappings_now if m.get("name")})

        cat_combo_var = tk.StringVar()
        cat_combo = ttk.Combobox(add_row, textvariable=cat_combo_var, values=known_cats, font=FL, width=24)
        cat_combo.pack(side="left", padx=(0, 6), ipady=4)
        cat_combo.set("Type or select a category...")

        def _add_category(e=None):
            raw = cat_combo_var.get().strip()
            if not raw or raw == "Type or select a category...":
                return
            changed = False
            for item in [x.strip() for x in raw.split(",") if x.strip()]:
                if item and item not in current_categories:
                    current_categories.append(item)
                    changed = True
            if changed:
                _rebuild_chips()
                _update_live_count()
            cat_combo_var.set("")
            cat_combo.set("Type or select a category...")

        cat_combo.bind("<Return>", _add_category)
        cat_combo.bind("<<ComboboxSelected>>", _add_category)
        self._btn(add_row, "+ Add Category", _add_category, bg=ACCENT2).pack(side="left")

        # Quick Add Pills
        quick_fr = tk.Frame(cat_section, bg=BG)
        quick_fr.pack(fill="x", pady=(6, 0))
        tk.Label(quick_fr, text="Quick Add:", font=("Segoe UI", 8, "bold"), bg=BG, fg=MUTED).pack(side="left", padx=(0, 6))

        for qc in ["Motor", "Cables", "Electrodes", "VFD", "Welding", "Wire", "LED", "Nickel", "Screen", "Jointing"]:
            def _qfn(kw=qc):
                def _q():
                    if kw not in current_categories:
                        current_categories.append(kw)
                        _rebuild_chips()
                        _update_live_count()
                return _q
            tk.Button(quick_fr, text=qc, command=_qfn(), bg=CARD, fg=TEXTSUB, relief="flat",
                      font=("Segoe UI", 8), padx=6, pady=3, activebackground=ACCENT2,
                      activeforeground=TEXT, cursor="hand2", bd=0).pack(side="left", padx=(0, 3), pady=2)

        # ── Matching Settings ──
        _section_header(form_fr, "⚙️", "Matching Settings")
        loc_var, _ = _field(form_fr, "Location Keywords", "comma-separated (blank = all locations)")
        exc_var, _ = _field(form_fr, "Exclude Keywords", "comma-separated (tenders with these are skipped)")

        # ── Compliance Documents Vault ──
        _doc_hdr_fr = tk.Frame(form_fr, bg=BG)
        _doc_hdr_fr.pack(fill="x", pady=(16, 4))
        
        ttk.Separator(_doc_hdr_fr, orient="horizontal").pack(fill="x", pady=(0, 6))
        _doc_title_fr = tk.Frame(_doc_hdr_fr, bg=BG)
        _doc_title_fr.pack(fill="x")
        
        tk.Label(_doc_title_fr, text="📂", font=("Segoe UI", 11), bg=BG, fg=TEXT).pack(side="left", padx=(0, 6))
        tk.Label(_doc_title_fr, text="Document Vault & Expiration Tracking", font=("Segoe UI", 9, "bold"), bg=BG, fg=TEXT).pack(side="left")
        tk.Label(_doc_title_fr, text="optional fields marked ★", font=("Segoe UI", 8), bg=BG, fg=TEXTSUB).pack(side="left", padx=(8, 0))

        # 📁 Auto-Scan Folder Button
        def _auto_scan_firm_folder():
            folder = filedialog.askdirectory(title=f"Select Documents Folder for {name_var.get() or 'Firm'}", parent=self)
            if not folder:
                return

            scanned = 0
            doc_rules = {
                "gst": ["gst"],
                "pan": ["pan"],
                "msme": ["msme", "udyam"],
                "itr_1": ["itr_1", "itr 1", "itr_2023", "itr_year_1"],
                "itr_2": ["itr_2", "itr 2", "itr_2024", "itr_year_2"],
                "itr_3": ["itr_3", "itr 3", "itr_2025", "itr_year_3"],
                "bs_1": ["balance_sheet_1", "bs_1", "balance sheet 1"],
                "bs_2": ["balance_sheet_2", "bs_2", "balance sheet 2"],
                "bs_3": ["balance_sheet_3", "bs_3", "balance sheet 3"],
                "turnover_cert": ["turnover"],
                "shareholder": ["shareholder"]
            }

            for root_dir, _, files in os.walk(folder):
                for filename in files:
                    file_lower = filename.lower()
                    full_path = os.path.join(root_dir, filename)
                    for doc_key, keywords in doc_rules.items():
                        if not doc_vars[doc_key].get().strip():
                            if any(kw in file_lower for kw in keywords):
                                doc_vars[doc_key].set(full_path)
                                scanned += 1
                                # Regex search for embedded expiry date (YYYY-MM-DD)
                                m = re.search(r'(\d{4}[_\-\/]\d{2}[_\-\/]\d{2})', filename)
                                if m:
                                    expiry_vars[doc_key].set(m.group(1).replace('/', '-'))

            if scanned > 0:
                messagebox.showinfo("Auto-Scan Complete", f"Found and linked {scanned} document(s) from:\n{folder}", parent=self)
            else:
                messagebox.showwarning("No Matches Found", f"No matching compliance documents found in:\n{folder}\n\nTip: File names should contain keywords like GST, PAN, MSME, ITR, Balance Sheet, Turnover.", parent=self)

        self._btn(_doc_title_fr, "📁 Auto-Scan Folder", _auto_scan_firm_folder, bg="#1C3557", fg="#79C0FF").pack(side="right", padx=(0, 4))

        # Progress bar row
        prog_fr = tk.Frame(form_fr, bg=BG)
        prog_fr.pack(fill="x", pady=(4, 8))
        prog_text_var = tk.StringVar(value="")
        prog_lbl = tk.Label(prog_fr, textvariable=prog_text_var, font=("Segoe UI", 8, "bold"), bg=BG, fg=MUTED)
        prog_lbl.pack(side="left")
        prog_canvas = tk.Canvas(prog_fr, bg=CARD, highlightthickness=0, height=6, width=260)
        prog_canvas.pack(side="right")

        def _refresh_doc_progress():
            up = 0
            exp_count = 0
            for k in REQUIRED_KEYS:
                p = doc_vars.get(k, tk.StringVar()).get().strip()
                ex = expiry_vars.get(k, tk.StringVar()).get().strip()
                if p and os.path.exists(p):
                    up += 1
                    status_code, _, _ = _check_doc_status(p, ex)
                    if status_code == "EXPIRED":
                        exp_count += 1

            pct = up / TOTAL_REQUIRED
            w = prog_canvas.winfo_width() or 260
            bar_w = max(4, int(w * pct))
            prog_canvas.delete("all")
            prog_canvas.create_rectangle(0, 0, w, 6, fill=CARD, outline="")
            color = DOC_EXPIRED if exp_count > 0 else (DOC_UPLOADED if pct == 1.0 else (DOC_MISSING if pct > 0 else DOC_NONE))
            if bar_w > 0:
                prog_canvas.create_rectangle(0, 0, bar_w, 6, fill=color, outline="")
            
            exp_suffix = f" ({exp_count} Expired ⚠️)" if exp_count > 0 else ""
            prog_text_var.set(f"{up}/{TOTAL_REQUIRED} required docs{exp_suffix}")
            prog_lbl.configure(fg=DOC_EXPIRED if exp_count > 0 else (DOC_UPLOADED if pct == 1.0 else MUTED))

        prog_canvas.bind("<Configure>", lambda e: _refresh_doc_progress())

        docs_outer = tk.Frame(form_fr, bg=CARD, highlightthickness=1, highlightbackground=SECTION_LINE)
        docs_outer.pack(fill="x", pady=(0, 10))

        doc_vars = {}
        expiry_vars = {}

        def _make_doc_row(parent, key, icon, label, optional, row_idx):
            row_bg = ROW_ALT if row_idx % 2 == 0 else CARD
            row = tk.Frame(parent, bg=row_bg)
            row.pack(fill="x")

            left_col = tk.Frame(row, bg=row_bg, width=190)
            left_col.pack(side="left", padx=(8, 4), pady=6)
            left_col.pack_propagate(False)

            icon_lbl = tk.Label(left_col, text=icon, font=("Segoe UI", 11), bg=row_bg, fg=TEXT)
            icon_lbl.pack(side="left", padx=(0, 5))

            opt_marker = " ★" if optional else ""
            tk.Label(left_col, text=f"{label}{opt_marker}",
                     font=("Segoe UI", 8, "italic" if optional else "normal"),
                     bg=row_bg, fg=TEXTSUB if optional else TEXT, anchor="w").pack(side="left", fill="x")

            mid_col = tk.Frame(row, bg=row_bg)
            mid_col.pack(side="left", fill="x", expand=True, padx=(0, 4))

            path_var = tk.StringVar(value="")
            expiry_var = tk.StringVar(value="")
            doc_vars[key] = path_var
            expiry_vars[key] = expiry_var

            status_lbl = tk.Label(mid_col, text="Not uploaded", font=("Segoe UI", 8), bg=row_bg, fg=TEXTSUB, anchor="w", cursor="hand2")
            status_lbl.pack(side="left", fill="x", expand=True)

            # Expiry date entry field
            exp_fr = tk.Frame(row, bg=row_bg)
            exp_fr.pack(side="left", padx=(0, 6))
            tk.Label(exp_fr, text="Exp:", font=("Segoe UI", 7), bg=row_bg, fg=MUTED).pack(side="left", padx=(0, 2))
            exp_ent = tk.Entry(exp_fr, textvariable=expiry_var, bg=CARD, fg=TEXT, insertbackground=TEXT,
                               relief="flat", font=("Segoe UI", 8), width=10, highlightthickness=1,
                               highlightbackground=SECTION_LINE, highlightcolor=ACCENT2)
            exp_ent.pack(side="left", ipady=2)

            def _update_display(pv=path_var, ev=expiry_var, sl=status_lbl, rbg=row_bg):
                p = pv.get().strip()
                ex = ev.get().strip()
                status_code, status_text, color = _check_doc_status(p, ex)
                if status_code in ("VALID", "EXPIRING", "EXPIRED"):
                    base = os.path.basename(p)
                    short = base[:22] + "..." if len(base) > 22 else base
                    sl.configure(text=f"{short} • [{status_text}]", fg=color, cursor="hand2")
                elif status_code == "MISSING":
                    sl.configure(text="⚠ File missing on disk", fg=DOC_MISSING)
                else:
                    sl.configure(text="Not uploaded", fg=TEXTSUB)
                _refresh_doc_progress()

            path_var.trace_add("write", lambda *a: _update_display())
            expiry_var.trace_add("write", lambda *a: _update_display())

            def _open_doc(pv=path_var):
                p = pv.get().strip()
                if p and os.path.exists(p):
                    try:
                        os.startfile(p)
                    except Exception:
                        import subprocess
                        try: subprocess.Popen(["xdg-open", p])
                        except Exception: pass
                elif p:
                    messagebox.showwarning("File Not Found", f"File no longer exists:\n{p}", parent=self)
                else:
                    messagebox.showinfo("No File", "No document uploaded yet.", parent=self)

            status_lbl.bind("<Button-1>", lambda e, pv=path_var: _open_doc(pv))

            btn_col = tk.Frame(row, bg=row_bg)
            btn_col.pack(side="right", padx=(0, 8), pady=4)

            def _upload(pv=path_var, ev=expiry_var, lbl=label):
                fpath = filedialog.askopenfilename(
                    title=f"Select {lbl}",
                    filetypes=[
                        ("Documents", "*.pdf *.PDF *.jpg *.jpeg *.png *.tiff *.tif *.bmp *.xlsx *.xls *.doc *.docx"),
                        ("PDF Files", "*.pdf *.PDF"),
                        ("All Files", "*.*"),
                    ],
                    parent=self
                )
                if fpath:
                    pv.set(fpath)
                    # Attempt regex date match on filename if expiry empty
                    if not ev.get().strip():
                        m = re.search(r'(\d{4}[_\-\/]\d{2}[_\-\/]\d{2})', os.path.basename(fpath))
                        if m:
                            ev.set(m.group(1).replace('/', '-'))

            def _clear(pv=path_var, ev=expiry_var):
                pv.set("")
                ev.set("")

            self._btn(btn_col, "📁 Upload", _upload, bg=UPLOAD_BG, fg="#79C0FF").pack(side="left", padx=(0, 4))
            self._btn(btn_col, "✕", _clear, bg=CARD, fg=ERR).pack(side="left")

        groups = [
            ("Identity & Registration", [(k, ic, lb, op) for k, ic, lb, op in DOCUMENT_TYPES if k in ("gst", "pan", "msme")]),
            ("Income Tax Returns (3 Years)", [(k, ic, lb, op) for k, ic, lb, op in DOCUMENT_TYPES if k.startswith("itr")]),
            ("Balance Sheets (3 Years)", [(k, ic, lb, op) for k, ic, lb, op in DOCUMENT_TYPES if k.startswith("bs")]),
            ("Financial Certificates", [(k, ic, lb, op) for k, ic, lb, op in DOCUMENT_TYPES if k in ("turnover_cert", "shareholder")]),
        ]

        row_idx = 0
        for g_title, g_rows in groups:
            g_hdr = tk.Frame(docs_outer, bg="#1A2029")
            g_hdr.pack(fill="x")
            tk.Label(g_hdr, text=f"  {g_title}", font=("Segoe UI", 7, "bold"), bg="#1A2029", fg=MUTED, anchor="w", pady=4).pack(fill="x")
            for key, icon, label, optional in g_rows:
                _make_doc_row(docs_outer, key, icon, label, optional, row_idx)
                row_idx += 1

        tk.Frame(docs_outer, bg=CARD, height=4).pack(fill="x")
        _refresh_doc_progress()

        # ── Form Action Buttons ──
        action_fr = tk.Frame(form_fr, bg=BG, pady=10)
        action_fr.pack(fill="x")
        _editing_idx = [None]

        def _save_current_firm():
            n = name_var.get().strip()
            if not n:
                messagebox.showerror("Error", "Firm Name is required.", parent=self)
                return
            if not current_categories:
                messagebox.showerror("Error", "Add at least one product category.", parent=self)
                return

            docs = {k: v.get().strip() for k, v in doc_vars.items() if v.get().strip()}
            exps = {k: v.get().strip() for k, v in expiry_vars.items() if v.get().strip()}
            fd = {
                "name": n,
                "categories": list(current_categories),
                "locations": loc_var.get().strip(),
                "exclude_keywords": exc_var.get().strip(),
                "documents": docs,
                "expiries": exps,
            }

            dup_idx = None
            for i, f in enumerate(firms_list):
                if i != _editing_idx[0] and f.get("name", "").strip().lower() == n.lower():
                    dup_idx = i
                    break

            if dup_idx is not None:
                firms_list[dup_idx] = fd
                if _editing_idx[0] is not None and _editing_idx[0] != dup_idx:
                    firms_list.pop(_editing_idx[0])
                new_idx = min(dup_idx, len(firms_list) - 1)
            elif _editing_idx[0] is None:
                firms_list.append(fd)
                new_idx = len(firms_list) - 1
            else:
                firms_list[_editing_idx[0]] = fd
                new_idx = _editing_idx[0]

            db.save_setting("firms", firms_list)
            _refresh_cards(selected=new_idx)
            _selected_idx[0] = new_idx
            _show_placeholder()
            _editing_idx[0] = None

        def _discard_form():
            _show_placeholder()
            _editing_idx[0] = None

        self._btn(action_fr, "💾 Save Firm", _save_current_firm, bg=ACCENT, fg="#FFFFFF").pack(side="left", padx=(0, 10), ipadx=8)
        self._btn(action_fr, "✕ Discard", _discard_form, bg=CARD).pack(side="left")

        # ── Show / Hide Helpers ──
        def _show_form(firm_data=None, idx=None):
            placeholder_fr.grid_forget()
            _form_canvas.grid(row=0, column=0, sticky="nsew")
            _form_scroll.grid(row=0, column=1, sticky="ns")
            right_fr.columnconfigure(1, weight=0)
            _form_canvas.yview_moveto(0)

            name_var.set(firm_data.get("name", "") if firm_data else "")
            loc_var.set(firm_data.get("locations", "") if firm_data else "")
            exc_var.set(firm_data.get("exclude_keywords", "") if firm_data else "")
            
            current_categories.clear()
            if firm_data:
                current_categories.extend(normalize_multi_value(firm_data.get("categories", [])))
            _rebuild_chips()
            _update_live_count()

            existing_docs = firm_data.get("documents", {}) if firm_data else {}
            existing_exps = firm_data.get("expiries", {}) if firm_data else {}
            for k, pv in doc_vars.items():
                pv.set(existing_docs.get(k, ""))
            for k, ev in expiry_vars.items():
                ev.set(existing_exps.get(k, ""))

            _refresh_doc_progress()
            _editing_idx[0] = idx
            name_ent.focus_set()

        def _show_placeholder():
            _form_canvas.grid_forget()
            _form_scroll.grid_forget()
            placeholder_fr.grid(row=0, column=0, sticky="nsew")
            _refresh_cards(selected=None)
            _selected_idx[0] = None

        # ── Left Button Bar ──
        def _delete_firm():
            idx = _selected_idx[0]
            if idx is None:
                messagebox.showwarning("Warning", "Select a firm first.", parent=self)
                return
            nm = firms_list[idx].get("name", "this firm").strip()
            if messagebox.askyesno("Confirm Delete", f"Delete firm '{nm}'?", parent=self):
                firms_list[:] = [f for f in firms_list if f.get("name", "").strip().lower() != nm.lower()]
                db.save_setting("firms", firms_list)
                _show_placeholder()

        self._btn(lbtn_fr, "+ Add Firm", lambda: _show_form(None, idx=None), bg=ACCENT, fg="#FFFFFF").pack(side="left", padx=(0, 4), fill="x", expand=True)
        self._btn(lbtn_fr, "🗑 Delete", _delete_firm, bg=CARD, fg=ERR).pack(side="left", fill="x", expand=True)

        _refresh_cards()

        # ── Bottom Bar Content ──
        def save_all_firms():
            db.save_setting("firms", firms_list)
            self._log("ok", f"Saved {len(firms_list)} firm(s) to settings.")

            def do_re_evaluate():
                settings_inner = db.load_settings()
                inc_raw = settings_inner.get("include_keywords", "")
                exc_raw = settings_inner.get("exclude_keywords", "")
                inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
                exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
                updated_count = 0
                for r in getattr(self.parent, '_records', []):
                    old_want = r.get("is_want_derived")
                    old_firm = r.get("matched_firm", "")
                    is_want = self.parent._get_tender_status(r, inc_kws, exc_kws) if hasattr(self.parent, '_get_tender_status') else True
                    r["is_want_derived"] = is_want
                    if (old_want != r.get("is_want_derived") or old_firm != r.get("matched_firm", "")):
                        updated_count += 1
                if updated_count > 0:
                    db.save_all_tenders(self.parent._records)
                self.after(0, self.parent._refresh_table_view if hasattr(self.parent, '_refresh_table_view') else lambda: None)
                self.after(0, lambda: self._log("ok", f"Re-evaluated: {updated_count} tender(s) updated."))

            LoadingDialog(self, title="Applying Firm Rules", message="Re-evaluating matching rules on all tenders...", task_fn=do_re_evaluate)
            self.destroy()

        self._btn(bot_fr, "✓ Save & Apply to All Tenders", save_all_firms, bg=ACCENT2, fg="#FFFFFF").pack(side="right", padx=20, ipadx=12, ipady=2)
        self._btn(bot_fr, "Cancel", self.destroy, bg=CARD).pack(side="right", padx=(0, 8))

    def _btn(self, *args, **kwargs):
        if hasattr(self.parent, '_btn'):
            return self.parent._btn(*args, **kwargs)
        bg = kwargs.pop('bg', CARD)
        fg = kwargs.pop('fg', TEXT)
        cmd = kwargs.pop('command', None) or (args[2] if len(args) > 2 else None)
        text = kwargs.pop('text', None) or (args[1] if len(args) > 1 else "")
        parent_w = args[0] if len(args) > 0 else self
        return tk.Button(parent_w, text=text, command=cmd, bg=bg, fg=fg, activebackground=PANEL, activeforeground=TEXT, font=("Segoe UI", 9), relief="flat", padx=10, pady=4, cursor="hand2", **kwargs)

    def _log(self, *args, **kwargs):
        if hasattr(self.parent, '_log'):
            return self.parent._log(*args, **kwargs)
        print("[Log]", *args)
