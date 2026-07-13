# -*- coding: utf-8 -*-
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Local imports
from config import BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, ERR, SUCCESS, FL
import db
from .loading_dialog import LoadingDialog

class FirmsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grab_set()
        self.transient(parent)
        self.title("Manage Firms")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(980, 660)

        x = parent.winfo_x() + (parent.winfo_width() - 1060) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 720) // 2
        self.geometry(f"1060x720+{max(0, x)}+{max(0, y)}")

        # ── Accent colours used only in this dialog ──────────────────────
        DOC_UPLOADED   = "#2EA043"   # green when file present
        DOC_MISSING    = "#D29922"   # amber when path saved but file gone
        DOC_NONE       = "#484F58"   # grey when nothing uploaded
        ROW_ALT        = "#1C2128"   # alternating doc-row background
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

        def _doc_completion(documents: dict) -> tuple:
            """Returns (uploaded_required, total_required, has_all_optional)."""
            uploaded = sum(1 for k in REQUIRED_KEYS if documents.get(k, "").strip())
            return uploaded, TOTAL_REQUIRED

        # Load firms from settings
        settings = db.load_settings()
        firms_list = []
        for firm in settings.get("firms", []):
            firms_list.append({
                "name": firm.get("name", ""),
                "categories": normalize_multi_value(firm.get("categories", [])),
                "locations": firm.get("locations", ""),
                "exclude_keywords": firm.get("exclude_keywords", ""),
                "documents": firm.get("documents", {}),
            })

        # ── Title bar ────────────────────────────────────────────────────
        title_bar = tk.Frame(self, bg=PANEL, pady=10,
                             highlightthickness=1, highlightbackground=SECTION_LINE)
        title_bar.pack(fill="x", side="top")
        tk.Label(title_bar, text="🏢  Manage Firms", font=("Segoe UI", 13, "bold"),
                 bg=PANEL, fg=TEXT).pack(side="left", padx=16)
        firm_count_var = tk.StringVar(value=f"{len(firms_list)} firm(s)")
        tk.Label(title_bar, textvariable=firm_count_var,
                 font=("Segoe UI", 9), bg=PANEL, fg=MUTED).pack(side="left", padx=(0, 0))

        # ── Bottom bar (packed before main so it stays pinned) ────────────
        bot_fr = tk.Frame(self, bg=PANEL, pady=10,
                          highlightthickness=1, highlightbackground=SECTION_LINE)
        bot_fr.pack(fill="x", side="bottom")

        # ── Main split ───────────────────────────────────────────────────
        main_fr = tk.Frame(self, bg=BG)
        main_fr.pack(fill="both", expand=True, padx=0, pady=0)
        main_fr.columnconfigure(0, weight=0, minsize=230)
        main_fr.columnconfigure(1, weight=1)
        main_fr.rowconfigure(0, weight=1)

        # ── LEFT: Firm list panel ────────────────────────────────────────
        left_fr = tk.Frame(main_fr, bg=PANEL,
                           highlightthickness=1, highlightbackground=SECTION_LINE)
        left_fr.grid(row=0, column=0, sticky="nsew")
        left_fr.rowconfigure(1, weight=1)
        left_fr.columnconfigure(0, weight=1)

        left_hdr = tk.Frame(left_fr, bg=PANEL, pady=8)
        left_hdr.grid(row=0, column=0, sticky="ew", padx=10)
        tk.Label(left_hdr, text="FIRMS", font=("Segoe UI", 8, "bold"),
                 bg=PANEL, fg=MUTED).pack(side="left")

        # Scrollable custom listbox area
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

        ttk.Separator(left_fr, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew")
        lbtn_fr = tk.Frame(left_fr, bg=PANEL, pady=8)
        lbtn_fr.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8)

        # Track selected index for custom card list
        _selected_idx = [None]
        _card_frames  = []  # list of (outer_frame, inner widgets)

        def _make_firm_card(idx, firm_data, selected=False):
            """Build a single firm card widget inside list_inner."""
            card_bg  = ACCENT2 + "22" if selected else PANEL   # subtle blue tint
            border_c = ACCENT2 if selected else SECTION_LINE

            outer = tk.Frame(list_inner, bg=border_c,
                             highlightthickness=0, pady=1)
            outer.pack(fill="x", padx=6, pady=3)

            inner = tk.Frame(outer, bg=card_bg if selected else CARD,
                             padx=10, pady=8, cursor="hand2")
            inner.pack(fill="x")

            name = firm_data.get("name", "Unnamed")
            cats = firm_data.get("categories", [])
            docs = firm_data.get("documents", {})
            up, tot = _doc_completion(docs)
            cat_cnt = len(cats) if isinstance(cats, list) else len(normalize_multi_value(cats))

            name_lbl = tk.Label(inner, text=name,
                                font=("Segoe UI", 10, "bold" if selected else "normal"),
                                bg=inner.cget("bg"), fg=TEXT if selected else TEXT,
                                anchor="w")
            name_lbl.pack(fill="x")

            meta_fr = tk.Frame(inner, bg=inner.cget("bg"))
            meta_fr.pack(fill="x", pady=(3, 0))

            # Category badge
            cat_badge = tk.Label(meta_fr,
                                 text=f"  {cat_cnt} cat  ",
                                 font=("Segoe UI", 7, "bold"),
                                 bg="#238636", fg="#AFFFB0",
                                 padx=2, pady=1)
            cat_badge.pack(side="left", padx=(0, 4))

            # Docs badge
            doc_color = "#238636" if up == tot else ("#D29922" if up > 0 else CARD)
            doc_fg    = "#AFFFB0" if up == tot else ("#FFE08A" if up > 0 else MUTED)
            doc_badge = tk.Label(meta_fr,
                                 text=f"  {up}/{tot} docs  ",
                                 font=("Segoe UI", 7, "bold"),
                                 bg=doc_color, fg=doc_fg,
                                 padx=2, pady=1)
            doc_badge.pack(side="left")

            # Click binding — all children
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
            for i, f in enumerate(firms_list):
                card = _make_firm_card(i, f, selected=(i == selected))
                _card_frames.append(card)
            if not firms_list:
                tk.Label(list_inner, text="No firms yet",
                         font=FL, bg=PANEL, fg=MUTED).pack(pady=20)
            firm_count_var.set(f"{len(firms_list)} firm(s)")

        # ── RIGHT: Scrollable form ────────────────────────────────────────
        right_fr = tk.Frame(main_fr, bg=BG)
        right_fr.grid(row=0, column=1, sticky="nsew")
        right_fr.columnconfigure(0, weight=1)
        right_fr.rowconfigure(0, weight=1)

        # Placeholder
        placeholder_fr = tk.Frame(right_fr, bg=BG)
        placeholder_fr.grid(row=0, column=0, sticky="nsew")
        placeholder_fr.rowconfigure(0, weight=1)
        placeholder_fr.columnconfigure(0, weight=1)
        tk.Label(placeholder_fr,
                 text="🏢",
                 font=("Segoe UI", 48), bg=BG, fg="#30363D"
                 ).grid(row=0, column=0, pady=(60, 4))
        tk.Label(placeholder_fr,
                 text="Select a firm from the left\nor click  + Add  to create one",
                 font=("Segoe UI", 11), bg=BG, fg=MUTED, justify="center"
                 ).grid(row=1, column=0)

        # Scrollable canvas
        _form_canvas = tk.Canvas(right_fr, bg=BG, highlightthickness=0)
        _form_scroll = ttk.Scrollbar(right_fr, orient="vertical", command=_form_canvas.yview)
        _form_canvas.configure(yscrollcommand=_form_scroll.set)

        form_fr = tk.Frame(_form_canvas, bg=BG, padx=18, pady=10)
        _form_win = _form_canvas.create_window((0, 0), window=form_fr, anchor="nw")

        def _on_form_configure(e):
            _form_canvas.configure(scrollregion=_form_canvas.bbox("all"))
        def _on_canvas_configure(e):
            _form_canvas.itemconfig(_form_win, width=e.width)
        form_fr.bind("<Configure>", _on_form_configure)
        _form_canvas.bind("<Configure>", _on_canvas_configure)

        def _bind_mw(widget):
            widget.bind("<MouseWheel>",
                lambda e: _form_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
            for ch in widget.winfo_children():
                _bind_mw(ch)
        form_fr.bind("<Map>", lambda e: _bind_mw(form_fr))

        # ── Helper: section header ────────────────────────────────────────
        def _section_header(parent, icon, title, subtitle=None):
            fr = tk.Frame(parent, bg=BG)
            fr.pack(fill="x", pady=(16, 6))
            ttk.Separator(fr, orient="horizontal").pack(fill="x", pady=(0, 6))
            hdr = tk.Frame(fr, bg=BG)
            hdr.pack(fill="x")
            tk.Label(hdr, text=icon, font=("Segoe UI", 11),
                     bg=BG, fg=TEXT).pack(side="left", padx=(0, 6))
            tk.Label(hdr, text=title, font=("Segoe UI", 9, "bold"),
                     bg=BG, fg=TEXT).pack(side="left")
            if subtitle:
                tk.Label(hdr, text=subtitle, font=("Segoe UI", 8),
                         bg=BG, fg=TEXTSUB).pack(side="left", padx=(10, 0))

        # ── Helper: field row ─────────────────────────────────────────────
        def _field(parent, label, hint=None):
            fr = tk.Frame(parent, bg=BG)
            fr.pack(fill="x", pady=(0, 10))
            lbl_fr = tk.Frame(fr, bg=BG)
            lbl_fr.pack(fill="x")
            tk.Label(lbl_fr, text=label, font=("Segoe UI", 8, "bold"),
                     bg=BG, fg=MUTED).pack(side="left")
            if hint:
                tk.Label(lbl_fr, text=hint, font=("Segoe UI", 7),
                         bg=BG, fg=TEXTSUB).pack(side="left", padx=(8, 0))
            var = tk.StringVar()
            ent = tk.Entry(fr, textvariable=var, bg=CARD, fg=TEXT,
                           insertbackground=TEXT, relief="flat",
                           font=("Segoe UI", 10),
                           highlightthickness=1,
                           highlightbackground=SECTION_LINE,
                           highlightcolor=ACCENT2)
            ent.pack(fill="x", pady=(4, 0), ipady=6)
            return var, ent

        # ── Firm Name ─────────────────────────────────────────────────────
        nm_hdr = tk.Frame(form_fr, bg=BG)
        nm_hdr.pack(fill="x", pady=(0, 4))
        tk.Label(nm_hdr, text="Firm Name", font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=MUTED).pack(side="left")
        name_var = tk.StringVar()
        name_ent = tk.Entry(form_fr, textvariable=name_var, bg=CARD, fg=TEXT,
                            insertbackground=TEXT, relief="flat",
                            font=("Segoe UI", 12, "bold"),
                            highlightthickness=1,
                            highlightbackground=SECTION_LINE,
                            highlightcolor=ACCENT2)
        name_ent.pack(fill="x", pady=(0, 4), ipady=7)

        # ── Categories section ────────────────────────────────────────────
        _section_header(form_fr, "🏷️", "Product Categories",
                        "tenders are matched against these keywords")

        cat_section = tk.Frame(form_fr, bg=BG)
        cat_section.pack(fill="x", pady=(0, 4))

        cat_hdr_fr = tk.Frame(cat_section, bg=BG)
        cat_hdr_fr.pack(fill="x")
        live_match_lbl = tk.Label(cat_hdr_fr, text="", font=("Segoe UI", 8),
                                  bg=BG, fg=SUCCESS)
        live_match_lbl.pack(side="right", padx=4)

        # Chips panel
        chips_outer = tk.Frame(cat_section, bg=CARD,
                               highlightthickness=1, highlightbackground=SECTION_LINE)
        chips_outer.pack(fill="x", pady=(4, 0))

        chips_canvas = tk.Canvas(chips_outer, bg=CARD, highlightthickness=0, height=110)
        chips_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        chips_frame = tk.Frame(chips_canvas, bg=CARD)
        chips_window = chips_canvas.create_window((0, 0), window=chips_frame, anchor="nw")
        chips_frame.bind("<Configure>",
            lambda e: chips_canvas.configure(scrollregion=chips_canvas.bbox("all")))
        chips_canvas.bind("<Configure>",
            lambda e: chips_canvas.itemconfig(chips_window, width=e.width))

        current_categories = []

        def _update_live_count():
            try:
                cats = [c.lower() for c in current_categories if c]
                if not cats:
                    live_match_lbl.configure(text="")
                    return
                count = sum(
                    1 for r in self.parent._records
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
                chip = tk.Frame(row_fr, bg=CHIP_BG,
                                highlightthickness=1, highlightbackground=ACCENT2)
                chip.pack(side="left", padx=(0, 6), pady=1)
                tk.Label(chip, text=cat, font=("Segoe UI", 9),
                         bg=CHIP_BG, fg=CHIP_FG, padx=6, pady=3).pack(side="left")
                def _make_rm(idx=i):
                    def _rm():
                        current_categories.pop(idx)
                        _rebuild_chips()
                        _update_live_count()
                    return _rm
                tk.Button(chip, text="×", command=_make_rm(),
                          bg=CHIP_BG, fg=ERR, relief="flat",
                          font=("Segoe UI", 9, "bold"), padx=4, pady=2,
                          activebackground="#2D2D2D", cursor="hand2", bd=0
                          ).pack(side="right")
                col += 1
            if not current_categories:
                tk.Label(chips_frame, text="No categories yet — add below",
                         font=FL, bg=CARD, fg=MUTED).pack(padx=8, pady=12)
            chips_frame.update_idletasks()
            chips_canvas.configure(scrollregion=chips_canvas.bbox("all"))

        # Add category row
        add_row = tk.Frame(cat_section, bg=BG)
        add_row.pack(fill="x", pady=(8, 0))

        settings_now = db.load_settings()
        mappings_now = settings_now.get("category_mappings") or []
        known_cats = sorted({m["name"] for m in mappings_now if m.get("name")})

        cat_combo_var = tk.StringVar()
        cat_combo = ttk.Combobox(add_row, textvariable=cat_combo_var,
                                 values=known_cats, font=FL, width=24)
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
        self._btn(add_row, "+ Add", _add_category, bg=ACCENT2).pack(side="left")

        # Quick-add pills
        quick_fr = tk.Frame(cat_section, bg=BG)
        quick_fr.pack(fill="x", pady=(6, 0))
        tk.Label(quick_fr, text="Quick:", font=("Segoe UI", 8),
                 bg=BG, fg=MUTED).pack(side="left", padx=(0, 6))
        for qc in ["Motor", "Cables", "Electrodes", "VFD", "Welding",
                   "Wire", "LED", "Nickel", "Screen", "Jointing", "Carbon Brush"]:
            def _qfn(kw=qc):
                def _q():
                    if kw not in current_categories:
                        current_categories.append(kw)
                        _rebuild_chips()
                        _update_live_count()
                return _q
            tk.Button(quick_fr, text=qc, command=_qfn(),
                      bg=CARD, fg=TEXTSUB, relief="flat", font=("Segoe UI", 8),
                      padx=6, pady=3, activebackground=ACCENT2,
                      activeforeground=TEXT, cursor="hand2", bd=0
                      ).pack(side="left", padx=(0, 3), pady=2)

        # ── Matching Settings section ─────────────────────────────────────
        _section_header(form_fr, "⚙️", "Matching Settings")

        loc_var, _ = _field(form_fr, "Location Keywords",
                            "comma-separated  (blank = all locations)")
        exc_var, _ = _field(form_fr, "Exclude Keywords",
                            "comma-separated  (tenders with these are skipped)")

        # ── Documents section ─────────────────────────────────────────────
        _section_header(form_fr, "📂", "Compliance Documents",
                        "optional fields marked ★")

        # Progress bar row
        prog_fr = tk.Frame(form_fr, bg=BG)
        prog_fr.pack(fill="x", pady=(0, 8))
        prog_text_var = tk.StringVar(value="")
        prog_lbl = tk.Label(prog_fr, textvariable=prog_text_var,
                            font=("Segoe UI", 8, "bold"), bg=BG, fg=MUTED)
        prog_lbl.pack(side="left")
        prog_canvas = tk.Canvas(prog_fr, bg=CARD, highlightthickness=0,
                                height=6, width=260)
        prog_canvas.pack(side="right")

        def _refresh_doc_progress():
            up = sum(1 for k in REQUIRED_KEYS if doc_vars.get(k, tk.StringVar()).get().strip())
            pct = up / TOTAL_REQUIRED
            w = prog_canvas.winfo_width() or 260
            bar_w = max(4, int(w * pct))
            prog_canvas.delete("all")
            prog_canvas.create_rectangle(0, 0, w, 6, fill=CARD, outline="")
            color = DOC_UPLOADED if pct == 1.0 else (DOC_MISSING if pct > 0 else DOC_NONE)
            if bar_w > 0:
                prog_canvas.create_rectangle(0, 0, bar_w, 6,
                                             fill=color, outline="")
            prog_text_var.set(f"{up}/{TOTAL_REQUIRED} required docs")
            prog_lbl.configure(fg=DOC_UPLOADED if pct == 1.0 else MUTED)

        prog_canvas.bind("<Configure>", lambda e: _refresh_doc_progress())

        docs_outer = tk.Frame(form_fr, bg=CARD,
                              highlightthickness=1, highlightbackground=SECTION_LINE)
        docs_outer.pack(fill="x", pady=(0, 10))

        doc_vars = {}

        def _make_doc_row(parent, key, icon, label, optional, row_idx):
            row_bg = ROW_ALT if row_idx % 2 == 0 else CARD
            row = tk.Frame(parent, bg=row_bg)
            row.pack(fill="x")

            # Left: icon + label
            left_col = tk.Frame(row, bg=row_bg, width=200)
            left_col.pack(side="left", padx=(10, 4), pady=6)
            left_col.pack_propagate(False)

            icon_lbl = tk.Label(left_col, text=icon,
                                font=("Segoe UI", 11), bg=row_bg, fg=TEXT)
            icon_lbl.pack(side="left", padx=(0, 5))

            opt_marker = " ★" if optional else ""
            tk.Label(left_col, text=f"{label}{opt_marker}",
                     font=("Segoe UI", 9, "italic" if optional else "normal"),
                     bg=row_bg,
                     fg=TEXTSUB if optional else TEXT,
                     anchor="w").pack(side="left", fill="x")

            # Middle: status indicator + filename
            mid_col = tk.Frame(row, bg=row_bg)
            mid_col.pack(side="left", fill="x", expand=True, padx=(0, 6))

            path_var = tk.StringVar(value="")
            doc_vars[key] = path_var

            status_dot = tk.Label(mid_col, text="●", font=("Segoe UI", 10),
                                  bg=row_bg, fg=DOC_NONE)
            status_dot.pack(side="left", padx=(0, 4))

            name_lbl = tk.Label(mid_col, text="Not uploaded",
                                font=("Segoe UI", 8), bg=row_bg, fg=TEXTSUB,
                                anchor="w", cursor="hand2")
            name_lbl.pack(side="left", fill="x", expand=True)

            def _update_display(pv=path_var, nl=name_lbl, sd=status_dot, rbg=row_bg):
                p = pv.get().strip()
                if p and os.path.exists(p):
                    base = os.path.basename(p)
                    short = base[:36] + "..." if len(base) > 36 else base
                    nl.configure(text=short, fg=DOC_UPLOADED, cursor="hand2")
                    sd.configure(fg=DOC_UPLOADED)
                elif p:
                    nl.configure(text="⚠ File missing", fg=DOC_MISSING)
                    sd.configure(fg=DOC_MISSING)
                else:
                    nl.configure(text="Not uploaded", fg=TEXTSUB)
                    sd.configure(fg=DOC_NONE)
                _refresh_doc_progress()

            path_var.trace_add("write",
                lambda *a, pv=path_var, nl=name_lbl, sd=status_dot:
                    _update_display(pv, nl, sd))

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
                    messagebox.showwarning(
                        "File Not Found", f"File no longer exists:\n{p}", parent=self)
                else:
                    messagebox.showinfo(
                        "No File", "No document uploaded yet.", parent=self)

            name_lbl.bind("<Button-1>", lambda e, pv=path_var: _open_doc(pv))

            # Right: Upload / Clear buttons
            btn_col = tk.Frame(row, bg=row_bg)
            btn_col.pack(side="right", padx=(0, 8), pady=4)

            def _upload(pv=path_var, lbl=label):
                fpath = filedialog.askopenfilename(
                    title=f"Select {lbl}",
                    filetypes=[
                        ("Documents",
                         "*.pdf *.PDF *.jpg *.jpeg *.png *.tiff *.tif"
                         " *.bmp *.xlsx *.xls *.doc *.docx"),
                        ("PDF Files", "*.pdf *.PDF"),
                        ("Images", "*.jpg *.jpeg *.png *.tiff *.tif *.bmp"),
                        ("All Files", "*.*"),
                    ],
                    parent=self
                )
                if fpath:
                    pv.set(fpath)

            def _clear(pv=path_var):
                pv.set("")

            self._btn(btn_col, "📁  Upload", _upload,
                      bg=UPLOAD_BG, fg="#79C0FF").pack(side="left", padx=(0, 4))
            self._btn(btn_col, "✕", _clear,
                      bg=CARD, fg=ERR).pack(side="left")

        # Draw doc rows with thin separator between groups
        groups = [
            ("Identity & Registration",
             [(k, ic, lb, op) for k, ic, lb, op in DOCUMENT_TYPES
              if k in ("gst", "pan", "msme")]),
            ("Income Tax Returns (3 Years)",
             [(k, ic, lb, op) for k, ic, lb, op in DOCUMENT_TYPES
              if k.startswith("itr")]),
            ("Balance Sheets (3 Years)",
             [(k, ic, lb, op) for k, ic, lb, op in DOCUMENT_TYPES
              if k.startswith("bs")]),
            ("Financial Certificates",
             [(k, ic, lb, op) for k, ic, lb, op in DOCUMENT_TYPES
              if k in ("turnover_cert", "shareholder")]),
        ]

        row_idx = 0
        for g_title, g_rows in groups:
            # Group sub-header inside the card
            g_hdr = tk.Frame(docs_outer, bg="#1A2029")
            g_hdr.pack(fill="x")
            tk.Label(g_hdr, text=f"  {g_title}",
                     font=("Segoe UI", 7, "bold"),
                     bg="#1A2029", fg=MUTED,
                     anchor="w", pady=4).pack(fill="x")
            for key, icon, label, optional in g_rows:
                _make_doc_row(docs_outer, key, icon, label, optional, row_idx)
                row_idx += 1

        tk.Frame(docs_outer, bg=CARD, height=4).pack(fill="x")

        # Initial progress render
        _refresh_doc_progress()

        # ── Form action buttons ────────────────────────────────────────────
        action_fr = tk.Frame(form_fr, bg=BG, pady=8)
        action_fr.pack(fill="x")
        _editing_idx = [None]

        def _save_current_firm():
            n = name_var.get().strip()
            if not n:
                messagebox.showerror("Error", "Firm Name is required.", parent=self)
                return
            if not current_categories:
                messagebox.showerror(
                    "Error", "Add at least one product category.", parent=self)
                return
            docs = {k: v.get() for k, v in doc_vars.items() if v.get().strip()}
            fd = {
                "name": n,
                "categories": list(current_categories),
                "locations": loc_var.get().strip(),
                "exclude_keywords": exc_var.get().strip(),
                "documents": docs,
            }
            if _editing_idx[0] is None:
                firms_list.append(fd)
                new_idx = len(firms_list) - 1
            else:
                firms_list[_editing_idx[0]] = fd
                new_idx = _editing_idx[0]
            _refresh_cards(selected=new_idx)
            _selected_idx[0] = new_idx
            _show_placeholder()
            _editing_idx[0] = None

        def _discard_form():
            _show_placeholder()
            _editing_idx[0] = None

        self._btn(action_fr, "💾  Save Firm", _save_current_firm,
                  bg=ACCENT).pack(side="left", padx=(0, 10), ipadx=6)
        self._btn(action_fr, "✕  Discard", _discard_form,
                  bg=CARD).pack(side="left")

        # ── Show / hide helpers ───────────────────────────────────────────
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
                current_categories.extend(
                    normalize_multi_value(firm_data.get("categories", [])))
            _rebuild_chips()
            _update_live_count()
            existing_docs = firm_data.get("documents", {}) if firm_data else {}
            for k, pv in doc_vars.items():
                pv.set(existing_docs.get(k, ""))
            _refresh_doc_progress()
            _editing_idx[0] = idx
            name_ent.focus_set()

        def _show_placeholder():
            _form_canvas.grid_forget()
            _form_scroll.grid_forget()
            placeholder_fr.grid(row=0, column=0, sticky="nsew")
            _refresh_cards(selected=None)
            _selected_idx[0] = None

        # ── Left button bar ───────────────────────────────────────────────
        def _delete_firm():
            idx = _selected_idx[0]
            if idx is None:
                messagebox.showwarning(
                    "Warning", "Select a firm first.", parent=self)
                return
            nm = firms_list[idx].get("name", "this firm")
            if messagebox.askyesno(
                    "Confirm Delete", f"Delete '{nm}'?", parent=self):
                firms_list.pop(idx)
                _show_placeholder()

        self._btn(lbtn_fr, "+ Add", lambda: _show_form(None, idx=None),
                  bg=ACCENT).pack(side="left", padx=(0, 4), fill="x", expand=True)
        self._btn(lbtn_fr, "🗑 Delete", _delete_firm,
                  bg=CARD, fg=ERR).pack(side="left", fill="x", expand=True)

        _refresh_cards()

        # ── Bottom bar content ────────────────────────────────────────────
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
                for r in self.parent._records:
                    old_want = r.get("is_want_derived")
                    old_firm = r.get("matched_firm", "")
                    is_want = self.parent._get_tender_status(r, inc_kws, exc_kws)
                    r["is_want_derived"] = is_want
                    if (old_want != r.get("is_want_derived")
                            or old_firm != r.get("matched_firm", "")):
                        updated_count += 1
                if updated_count > 0:
                    db.save_all_tenders(self.parent._records)
                self.after(0, self.parent._refresh_table_view)
                if hasattr(self.parent, "_update_analytics"):
                    self.after(0, self.parent._update_analytics)
                if hasattr(self.parent, "_update_calendar"):
                    self.after(0, self.parent._update_calendar)
                    self.after(0, self.parent._update_details)
                self.after(0, lambda: self._log(
                    "ok", f"Re-evaluated: {updated_count} tender(s) updated."))

            LoadingDialog(self, title="Applying Rules",
                          message="Re-evaluating matching rules on all tenders...",
                          task_fn=do_re_evaluate)
            self.destroy()

        self._btn(bot_fr, "✓  Save & Apply to All Tenders", save_all_firms,
                  bg=ACCENT2).pack(side="right", padx=20, ipadx=12, ipady=2)
        self._btn(bot_fr, "Cancel", self.destroy,
                  bg=CARD).pack(side="right", padx=(0, 8))

    def _btn(self, *args, **kwargs):
        return self.parent._btn(*args, **kwargs)

    def _log(self, *args, **kwargs):
        return self.parent._log(*args, **kwargs)
