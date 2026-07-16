# -*- coding: utf-8 -*-
"""
BidResultDialog — Record the outcome of a filed bid and track competitors.

Features:
  • Paste & Parse: paste GEM financial evaluation text → auto-fills competitor table
  • Manual add/edit/delete of competitor rows
  • Mark your own row with a checkbox
  • Auto-computes price gap / % gap vs L1
  • Lessons learned free-text notes
  • Persists to bid_results + bid_competitors tables via db.*
"""
import re
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from config import (
    BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN,
    FL, FT, FB
)
import db
import logger


# ─── Parser ───────────────────────────────────────────────────────────────────

def parse_gem_evaluation_text(raw: str) -> list:
    """
    Parse raw pasted text from a GEM Financial Evaluation page.
    Returns a list of dicts:
        rank, seller_name, offered_items, total_price, mse_category, is_own_bid
    Handles formats like:
        1   R K ELECTRODES      Item Categories : SUPPLY OF ...   ` 375530.87   L1
        2   ZED CONTROL SYSTEM AND SWITCHGEAR  ( MSE Social Category: General )  ...  ` 430100.00  L2
    """
    competitors = []

    # Split into lines, collapse whitespace
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    # We'll scan for lines that start with a number (rank indicator)
    # and then accumulate context lines until the price line
    # Strategy: find all lines matching a price pattern "` NNN" or "Rs. NNN"
    price_pat = re.compile(r"[`₹\u20b9]\s*([\d,]+\.?\d*)")
    rank_pat = re.compile(r"^\s*(\d+)\s+(.+)")
    l_rank_pat = re.compile(r"\bL(\d+)\b")
    mse_pat = re.compile(r"MSE Social Category\s*:\s*([^\)]+)", re.IGNORECASE)
    items_pat = re.compile(r"Item Categor(?:y|ies)\s*:\s*(.+)", re.IGNORECASE)

    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect a row start: line beginning with a digit (the S.No.)
        m_rank = rank_pat.match(line)
        if m_rank:
            sno = int(m_rank.group(1))
            rest = m_rank.group(2).strip()

            # Extract MSE category from the opening line or next lines
            mse_cat = ""
            m_mse = mse_pat.search(rest)
            if m_mse:
                mse_cat = m_mse.group(1).strip().rstrip(")")
            rest_clean = re.sub(r"\(\s*MSE Social Category[^\)]*\)", "", rest).strip()
            seller_name = rest_clean

            # Look ahead for item categories and price
            offered_items = ""
            price_val = None
            l_rank = sno  # default rank = S.No.

            j = i + 1
            while j < len(lines) and j < i + 8:
                nxt = lines[j]

                # Check for MSE in subsequent lines
                if not mse_cat:
                    m_mse2 = mse_pat.search(nxt)
                    if m_mse2:
                        mse_cat = m_mse2.group(1).strip().rstrip(")")

                # Item categories line
                m_items = items_pat.search(nxt)
                if m_items:
                    offered_items = m_items.group(1).strip()

                # Price line
                m_price = price_pat.search(nxt)
                if m_price:
                    price_str = m_price.group(1).replace(",", "")
                    try:
                        price_val = float(price_str)
                    except ValueError:
                        pass

                    # Rank from L-indicator on same line
                    m_lr = l_rank_pat.search(nxt)
                    if m_lr:
                        l_rank = int(m_lr.group(1))

                    i = j  # advance outer pointer past price line
                    break

                j += 1

            if price_val is not None:
                competitors.append({
                    "rank": l_rank,
                    "seller_name": seller_name,
                    "offered_items": offered_items,
                    "total_price": price_val,
                    "mse_category": mse_cat,
                    "is_own_bid": False,
                })

        i += 1

    # Sort by rank
    competitors.sort(key=lambda c: c["rank"])
    return competitors


# ─── Dialog ───────────────────────────────────────────────────────────────────

class BidResultDialog(tk.Toplevel):
    """Full-featured dialog for recording a bid's competitive outcome."""

    # Result options
    RESULTS = ["Pending", "Won", "Lost"]
    # Colors per result
    RESULT_COLORS = {"Won": SUCCESS, "Lost": ERR, "Pending": WARN}

    def __init__(self, parent, app, bid_no: str, on_save=None):
        super().__init__(parent)
        self.app = app
        self.bid_no = bid_no
        self.on_save = on_save  # callback(bid_no) after save

        self.title(f"📊 Bid Result — {bid_no}")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.geometry("940x680")
        self.minsize(800, 580)

        # Data state
        self._competitors = []       # list of dicts
        self._own_bid_idx = None     # row index of our own bid

        self._build_ui()
        self._load_existing()

        # Center on parent
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2 - self.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{max(0,px)}+{max(0,py)}")
        self.transient(parent)
        self.grab_set()

    # ── UI Build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Top strip ────────────────────────────────────────────────────────
        top = tk.Frame(self, bg=PANEL, padx=14, pady=10)
        top.pack(fill="x")

        tk.Label(
            top, text=f"📊  BID RESULT & COMPETITOR ANALYSIS",
            font=FT, bg=PANEL, fg=TEXT
        ).pack(side="left")

        tk.Label(
            top, text=self.bid_no,
            font=(FL[0], 9, "bold"), bg=PANEL, fg=ACCENT2
        ).pack(side="left", padx=(12, 0))

        # ── Main two-column body ──────────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=8)

        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        right = tk.Frame(body, bg=BG, width=280)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self._build_competitor_section(left)
        self._build_outcome_section(right)

        # ── Bottom bar ────────────────────────────────────────────────────────
        bot = tk.Frame(self, bg=PANEL, padx=14, pady=8)
        bot.pack(fill="x", side="bottom")

        self._gap_lbl = tk.Label(
            bot, text="", font=(FL[0], 9, "bold"), bg=PANEL, fg=MUTED
        )
        self._gap_lbl.pack(side="left")

        tk.Button(
            bot, text="  Cancel  ", font=FL, bg=CARD, fg=MUTED,
            relief="flat", bd=0, padx=8, pady=4,
            activebackground="#30363D", activeforeground=TEXT,
            cursor="hand2", command=self.destroy
        ).pack(side="right", padx=(6, 0))

        tk.Button(
            bot, text="  💾 Save Result  ", font=(FL[0], 9, "bold"),
            bg=ACCENT, fg="#FFFFFF", relief="flat", bd=0, padx=12, pady=4,
            activebackground="#2EA043", activeforeground="#FFFFFF",
            cursor="hand2", command=self._save
        ).pack(side="right")

    # ── Competitor Table Section ──────────────────────────────────────────────

    def _build_competitor_section(self, parent):
        hdr = tk.Frame(parent, bg=BG)
        hdr.pack(fill="x", pady=(0, 4))

        tk.Label(
            hdr, text="Competitor Financial Evaluation",
            font=(FL[0], 9, "bold"), bg=BG, fg=ACCENT2
        ).pack(side="left")

        # Toolbar buttons
        def _btn(text, cmd, fg=TEXT, bg=CARD):
            return tk.Button(
                hdr, text=text, font=FL, bg=bg, fg=fg,
                relief="flat", bd=0, padx=6, pady=3,
                activebackground="#30363D", activeforeground=TEXT,
                cursor="hand2", command=cmd
            )

        _btn("➕ Add Row", self._add_row).pack(side="right", padx=2)
        _btn("🗑 Delete Selected", self._del_selected, fg=ERR).pack(side="right", padx=2)
        _btn("📋 Paste & Parse", self._paste_parse, fg=ACCENT2, bg="#1A2D4C").pack(side="right", padx=2)

        # Treeview frame
        tv_fr = tk.Frame(parent, bg=BG)
        tv_fr.pack(fill="both", expand=True)

        cols = ("rank", "seller_name", "price", "mse_cat", "own")
        self.tv = ttk.Treeview(
            tv_fr, columns=cols, show="headings",
            selectmode="browse", height=14
        )
        self.tv.heading("rank",        text="Rank")
        self.tv.heading("seller_name", text="Seller Name")
        self.tv.heading("price",       text="Total Price (₹)")
        self.tv.heading("mse_cat",     text="MSE Category")
        self.tv.heading("own",         text="Our Bid ✓")

        self.tv.column("rank",        width=50,  minwidth=40,  anchor="center")
        self.tv.column("seller_name", width=300, minwidth=180, anchor="w")
        self.tv.column("price",       width=130, minwidth=100, anchor="e")
        self.tv.column("mse_cat",     width=110, minwidth=80,  anchor="center")
        self.tv.column("own",         width=70,  minwidth=50,  anchor="center")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
            background=CARD, fieldbackground=CARD, foreground=TEXT,
            rowheight=24, borderwidth=0, relief="flat"
        )
        style.configure("Treeview.Heading",
            background=PANEL, foreground=MUTED,
            font=(FL[0], 8, "bold"), relief="flat"
        )
        style.map("Treeview", background=[("selected", ACCENT2)])

        vsb = ttk.Scrollbar(tv_fr, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Tag colours
        self.tv.tag_configure("own_row",  background="#1A3A2A", foreground=SUCCESS)
        self.tv.tag_configure("l1_row",   background="#1A2D4C", foreground="#84D2FF")
        self.tv.tag_configure("odd_row",  background=CARD)
        self.tv.tag_configure("even_row", background="#1C2128")

        # Double-click to edit
        self.tv.bind("<Double-1>", self._on_double_click)

        # Hint label
        tk.Label(
            parent,
            text="💡 Double-click a row to edit  ·  Click 'Our Bid ✓' column to mark your row  ·  'Paste & Parse' auto-fills from GEM text",
            font=(FL[0], 7), bg=BG, fg=TEXTSUB, anchor="w"
        ).pack(fill="x", pady=(4, 0))

    # ── Outcome / Notes Section ───────────────────────────────────────────────

    def _build_outcome_section(self, parent):
        def section(text):
            f = tk.LabelFrame(
                parent, text=text, font=FL, bg=PANEL, fg=TEXTSUB,
                labelanchor="n", padx=8, pady=6,
                highlightthickness=1, highlightbackground="#30363D"
            )
            f.pack(fill="x", pady=(0, 8))
            return f

        # ─ Outcome ─
        out_fr = section("Bid Outcome")

        tk.Label(out_fr, text="Result:", font=FL, bg=PANEL, fg=MUTED).grid(row=0, column=0, sticky="w", pady=2)
        self.result_var = tk.StringVar(value="Pending")
        result_cb = ttk.Combobox(
            out_fr, textvariable=self.result_var,
            values=self.RESULTS, state="readonly", font=FL, width=12
        )
        result_cb.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=2)
        result_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_gap())

        tk.Label(out_fr, text="Our Price (₹):", font=FL, bg=PANEL, fg=MUTED).grid(row=1, column=0, sticky="w", pady=2)
        self.our_price_var = tk.StringVar()
        self.our_price_var.trace_add("write", lambda *a: self._refresh_gap())
        tk.Entry(
            out_fr, textvariable=self.our_price_var, bg=CARD, fg=TEXT,
            insertbackground=TEXT, relief="flat", font=FL, width=14,
            highlightthickness=1, highlightbackground="#30363D"
        ).grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=2)

        tk.Label(out_fr, text="Our Rank (L?):", font=FL, bg=PANEL, fg=MUTED).grid(row=2, column=0, sticky="w", pady=2)
        self.our_rank_var = tk.StringVar()
        self.our_rank_var.trace_add("write", lambda *a: self._refresh_gap())
        tk.Entry(
            out_fr, textvariable=self.our_rank_var, bg=CARD, fg=TEXT,
            insertbackground=TEXT, relief="flat", font=FL, width=14,
            highlightthickness=1, highlightbackground="#30363D"
        ).grid(row=2, column=1, sticky="ew", padx=(4, 0), pady=2)

        tk.Label(out_fr, text="L1 Price (₹):", font=FL, bg=PANEL, fg=MUTED).grid(row=3, column=0, sticky="w", pady=2)
        self.l1_price_var = tk.StringVar()
        self.l1_price_var.trace_add("write", lambda *a: self._refresh_gap())
        self._l1_ent = tk.Entry(
            out_fr, textvariable=self.l1_price_var, bg=CARD, fg=TEXT,
            insertbackground=TEXT, relief="flat", font=FL, width=14,
            highlightthickness=1, highlightbackground="#30363D"
        )
        self._l1_ent.grid(row=3, column=1, sticky="ew", padx=(4, 0), pady=2)

        out_fr.columnconfigure(1, weight=1)

        # ─ Price Gap Card ─
        gap_fr = section("Price Analysis")
        self._gap_price_lbl = tk.Label(gap_fr, text="—", font=(FL[0], 11, "bold"), bg=PANEL, fg=MUTED)
        self._gap_price_lbl.pack(fill="x")
        self._gap_pct_lbl = tk.Label(gap_fr, text="", font=(FL[0], 8), bg=PANEL, fg=TEXTSUB)
        self._gap_pct_lbl.pack(fill="x")

        # ─ Offered Items ─
        items_fr = section("Offered Items")
        self.items_var = tk.StringVar()
        tk.Entry(
            items_fr, textvariable=self.items_var, bg=CARD, fg=TEXT,
            insertbackground=TEXT, relief="flat", font=FL,
            highlightthickness=1, highlightbackground="#30363D"
        ).pack(fill="x")
        tk.Label(items_fr, text="(auto-filled from parse)", font=(FL[0], 7), bg=PANEL, fg=TEXTSUB).pack(anchor="w")

        # ─ Lessons Learned ─
        notes_fr = section("Lessons Learned / Notes")
        self.notes_txt = tk.Text(
            notes_fr, bg=CARD, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=FL, wrap="word", height=8,
            highlightthickness=1, highlightbackground="#30363D",
            padx=6, pady=4
        )
        self.notes_txt.pack(fill="both", expand=True)
        tk.Label(
            notes_fr,
            text="💬 What could you have done differently?\n    Note pricing strategy, missed qualifications, etc.",
            font=(FL[0], 7), bg=PANEL, fg=TEXTSUB, justify="left"
        ).pack(anchor="w", pady=(4, 0))

    # ── Load Existing Data ────────────────────────────────────────────────────

    def _load_existing(self):
        result = db.get_bid_result(self.bid_no)
        competitors = db.get_bid_competitors(self.bid_no)

        if result:
            self.result_var.set(result.get("result") or "Pending")
            if result.get("our_price") is not None:
                self.our_price_var.set(str(result["our_price"]))
            if result.get("our_rank") is not None:
                self.our_rank_var.set(str(result["our_rank"]))
            if result.get("l1_price") is not None:
                self.l1_price_var.set(str(result["l1_price"]))
            if result.get("notes"):
                self.notes_txt.insert("1.0", result["notes"])

        if competitors:
            self._competitors = competitors
            self._refresh_tv()

    # ── Competitor Table Helpers ──────────────────────────────────────────────

    def _refresh_tv(self):
        """Re-render the full treeview from self._competitors."""
        self.tv.delete(*self.tv.get_children())
        for idx, comp in enumerate(self._competitors):
            rank = comp.get("rank", idx + 1)
            name = comp.get("seller_name", "")
            price = comp.get("total_price")
            price_str = f"₹ {price:,.2f}" if price is not None else ""
            mse = comp.get("mse_category", "")
            own = "★ OUR BID" if comp.get("is_own_bid") else ""

            tags = []
            if comp.get("is_own_bid"):
                tags = ["own_row"]
            elif rank == 1:
                tags = ["l1_row"]
            elif idx % 2 == 0:
                tags = ["even_row"]
            else:
                tags = ["odd_row"]

            self.tv.insert("", "end", iid=str(idx),
                           values=(f"L{rank}", name, price_str, mse, own),
                           tags=tags)

        self._auto_fill_l1()
        self._refresh_gap()

    def _auto_fill_l1(self):
        """Auto-fill L1 price from competitor list."""
        for comp in self._competitors:
            if comp.get("rank") == 1:
                price = comp.get("total_price")
                if price is not None:
                    self.l1_price_var.set(str(price))
                break

    def _auto_fill_our_bid_fields(self):
        """Auto-fill our_price and our_rank from the marked own-bid row."""
        for comp in self._competitors:
            if comp.get("is_own_bid"):
                price = comp.get("total_price")
                rank = comp.get("rank")
                if price is not None:
                    self.our_price_var.set(str(price))
                if rank is not None:
                    self.our_rank_var.set(str(rank))
                # Also fill offered items
                items = comp.get("offered_items", "")
                if items:
                    self.items_var.set(items)
                break

    def _refresh_gap(self, *args):
        """Recompute price gap labels."""
        try:
            our = float(self.our_price_var.get().replace(",", "").strip())
            l1 = float(self.l1_price_var.get().replace(",", "").strip())
            gap = our - l1
            pct = (gap / l1 * 100) if l1 else 0.0
            sign = "+" if gap >= 0 else ""
            color = ERR if gap > 0 else SUCCESS if gap < 0 else MUTED
            self._gap_price_lbl.configure(
                text=f"Gap: {sign}₹ {gap:,.2f}",
                fg=color
            )
            self._gap_pct_lbl.configure(
                text=f"{sign}{pct:.2f}% vs L1",
                fg=color
            )
            self._gap_lbl.configure(
                text=f"Price gap vs L1:  {sign}₹ {gap:,.2f}  ({sign}{pct:.2f}%)",
                fg=color
            )
        except (ValueError, ZeroDivisionError):
            self._gap_price_lbl.configure(text="—", fg=MUTED)
            self._gap_pct_lbl.configure(text="", fg=TEXTSUB)
            self._gap_lbl.configure(text="", fg=MUTED)

    # ── Paste & Parse ─────────────────────────────────────────────────────────

    def _paste_parse(self):
        """Open paste window, parse pasted GEM text, populate competitor table."""
        pw = tk.Toplevel(self)
        pw.title("📋 Paste GEM Financial Evaluation Text")
        pw.configure(bg=BG)
        pw.geometry("700x480")
        pw.transient(self)
        pw.grab_set()

        tk.Label(
            pw,
            text="Paste the complete GEM Financial Evaluation section below.\n"
                 "Include S.No., Seller Name, Item Categories, prices and L-ranks.",
            font=FL, bg=BG, fg=MUTED, justify="left"
        ).pack(fill="x", padx=12, pady=(10, 4))

        txt_fr = tk.Frame(pw, bg=BG)
        txt_fr.pack(fill="both", expand=True, padx=12)

        paste_txt = tk.Text(
            txt_fr, bg=CARD, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=(FL[0], 9), wrap="word",
            highlightthickness=1, highlightbackground="#30363D",
            padx=8, pady=8
        )
        paste_txt.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(txt_fr, orient="vertical", command=paste_txt.yview)
        paste_txt.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        # Auto-paste from clipboard if available
        try:
            cb = pw.clipboard_get()
            if cb.strip():
                paste_txt.insert("1.0", cb)
        except Exception:
            pass

        status_lbl = tk.Label(pw, text="", font=FL, bg=BG, fg=MUTED)
        status_lbl.pack(fill="x", padx=12)

        bot = tk.Frame(pw, bg=PANEL, padx=12, pady=8)
        bot.pack(fill="x", side="bottom")

        def do_parse():
            raw = paste_txt.get("1.0", "end").strip()
            if not raw:
                status_lbl.configure(text="⚠  Nothing to parse.", fg=WARN)
                return
            parsed = parse_gem_evaluation_text(raw)
            if not parsed:
                status_lbl.configure(
                    text="⚠  Could not parse any competitor rows. "
                         "Make sure to include the full table with prices.",
                    fg=WARN
                )
                return
            # Merge into our list (replace all)
            self._competitors = parsed
            self._refresh_tv()
            status_lbl.configure(
                text=f"✔  Parsed {len(parsed)} competitor row(s) successfully.",
                fg=SUCCESS
            )
            # Auto-fill L1 + our bid if already marked
            self._auto_fill_our_bid_fields()

        def do_ok():
            do_parse()
            if self._competitors:
                pw.destroy()

        tk.Button(
            bot, text="  ✗ Cancel  ", font=FL, bg=CARD, fg=MUTED,
            relief="flat", bd=0, padx=8, pady=4, cursor="hand2",
            command=pw.destroy
        ).pack(side="right", padx=(4, 0))

        tk.Button(
            bot, text="  ✔ Parse & Apply  ", font=(FL[0], 9, "bold"),
            bg=ACCENT2, fg="#FFFFFF", relief="flat", bd=0, padx=12, pady=4,
            cursor="hand2", command=do_ok
        ).pack(side="right")

        tk.Button(
            bot, text="  🔍 Preview Parse  ", font=FL, bg=CARD, fg=ACCENT2,
            relief="flat", bd=0, padx=8, pady=4, cursor="hand2",
            command=do_parse
        ).pack(side="right", padx=4)

    # ── Row Edit (Double-click) ────────────────────────────────────────────────

    def _on_double_click(self, event):
        region = self.tv.identify_region(event.x, event.y)
        if region != "cell":
            return
        iid = self.tv.identify_row(event.y)
        if not iid:
            return
        col = self.tv.identify_column(event.x)

        try:
            idx = int(iid)
        except ValueError:
            return

        # Clicking "own" column toggles our-bid mark
        if col == "#5":
            self._toggle_own_bid(idx)
            return

        # Otherwise open edit dialog
        self._edit_row(idx)

    def _toggle_own_bid(self, idx):
        """Toggle is_own_bid on the clicked row; only one row can be own bid."""
        for i, comp in enumerate(self._competitors):
            comp["is_own_bid"] = (i == idx) and not self._competitors[idx].get("is_own_bid")
        self._refresh_tv()
        self._auto_fill_our_bid_fields()

    def _edit_row(self, idx):
        comp = self._competitors[idx]

        dlg = tk.Toplevel(self)
        dlg.title(f"Edit Row — L{comp.get('rank', idx+1)}")
        dlg.configure(bg=BG)
        dlg.geometry("460x340")
        dlg.transient(self)
        dlg.grab_set()

        fields = [
            ("Rank (L number)", "rank"),
            ("Seller Name", "seller_name"),
            ("Total Price (₹)", "total_price"),
            ("MSE Category", "mse_category"),
            ("Offered Items", "offered_items"),
        ]
        vars_ = {}
        for row, (label, key) in enumerate(fields):
            tk.Label(dlg, text=label + ":", font=FL, bg=BG, fg=MUTED).grid(
                row=row, column=0, sticky="w", padx=14, pady=4
            )
            v = tk.StringVar(value=str(comp.get(key) or ""))
            vars_[key] = v
            tk.Entry(
                dlg, textvariable=v, bg=CARD, fg=TEXT,
                insertbackground=TEXT, relief="flat", font=FL, width=28,
                highlightthickness=1, highlightbackground="#30363D"
            ).grid(row=row, column=1, sticky="ew", padx=(4, 14), pady=4)

        own_var = tk.BooleanVar(value=bool(comp.get("is_own_bid")))
        tk.Checkbutton(
            dlg, text="This is OUR BID", variable=own_var,
            bg=BG, fg=SUCCESS, selectcolor=CARD,
            activebackground=BG, activeforeground=SUCCESS, font=FL
        ).grid(row=len(fields), column=0, columnspan=2, padx=14, pady=8, sticky="w")

        dlg.columnconfigure(1, weight=1)

        def apply_():
            try:
                self._competitors[idx]["rank"] = int(vars_["rank"].get()) if vars_["rank"].get().strip() else idx + 1
            except ValueError:
                pass
            self._competitors[idx]["seller_name"] = vars_["seller_name"].get().strip()
            try:
                self._competitors[idx]["total_price"] = float(vars_["total_price"].get().replace(",", "").strip())
            except ValueError:
                pass
            self._competitors[idx]["mse_category"] = vars_["mse_category"].get().strip()
            self._competitors[idx]["offered_items"] = vars_["offered_items"].get().strip()
            if own_var.get():
                for i, c in enumerate(self._competitors):
                    c["is_own_bid"] = (i == idx)
            else:
                self._competitors[idx]["is_own_bid"] = False
            self._refresh_tv()
            self._auto_fill_our_bid_fields()
            dlg.destroy()

        bot = tk.Frame(dlg, bg=PANEL, padx=12, pady=8)
        bot.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="ew")
        dlg.rowconfigure(len(fields) + 1, weight=1)

        tk.Button(bot, text="Cancel", font=FL, bg=CARD, fg=MUTED, relief="flat",
                  bd=0, padx=8, pady=4, cursor="hand2", command=dlg.destroy).pack(side="right", padx=4)
        tk.Button(bot, text="✔ Apply", font=(FL[0], 9, "bold"), bg=ACCENT, fg="#FFF",
                  relief="flat", bd=0, padx=10, pady=4, cursor="hand2", command=apply_).pack(side="right")

    def _add_row(self):
        new_rank = len(self._competitors) + 1
        self._competitors.append({
            "rank": new_rank, "seller_name": "", "offered_items": "",
            "total_price": None, "mse_category": "", "is_own_bid": False
        })
        self._refresh_tv()
        self._edit_row(len(self._competitors) - 1)

    def _del_selected(self):
        sel = self.tv.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except ValueError:
            return
        del self._competitors[idx]
        self._refresh_tv()

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self):
        # Compute gap values
        try:
            our_price = float(self.our_price_var.get().replace(",", "").strip())
        except ValueError:
            our_price = None
        try:
            l1_price = float(self.l1_price_var.get().replace(",", "").strip())
        except ValueError:
            l1_price = None
        try:
            our_rank = int(self.our_rank_var.get().strip())
        except ValueError:
            our_rank = None

        price_gap = None
        price_gap_pct = None
        if our_price is not None and l1_price is not None and l1_price != 0:
            price_gap = our_price - l1_price
            price_gap_pct = price_gap / l1_price * 100

        result_dict = {
            "result": self.result_var.get(),
            "our_rank": our_rank,
            "our_price": our_price,
            "l1_price": l1_price,
            "price_gap": price_gap,
            "price_gap_pct": price_gap_pct,
            "notes": self.notes_txt.get("1.0", "end").strip(),
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
        }

        ok1 = db.save_bid_result(self.bid_no, result_dict)
        ok2 = db.save_bid_competitors(self.bid_no, self._competitors)

        if ok1 and ok2:
            logger.log_ok(f"Bid result saved for {self.bid_no}: {result_dict['result']}")
            if self.on_save:
                self.on_save(self.bid_no)
            self.destroy()
        else:
            messagebox.showerror(
                "Save Error",
                "Failed to save bid result. Check logs for details.",
                parent=self
            )
