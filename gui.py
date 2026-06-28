import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

# Local imports
from config import (
    BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN, SEL_BG,
    FH, FB, FL, FT, TV_COLS, TV_IDS
)
from excel import financial_year, xl_path, ensure_workbook, xl_append
from parser import split_blocks, parse_one
from scraper import scrape_bid_page, _try_import_selenium

class TenderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GEM Tender Logger  v4")
        self.configure(bg=BG)
        self.geometry("1400x860")
        self.minsize(900, 600)

        self.save_folder = tk.StringVar(
            value=os.path.expanduser("~\\Documents" if os.name=="nt" else "~/Documents"))
        self._records  = []
        self._editing  = None
        self._fetch_running = False

        self._style()
        self._build()
        self._fy_tick()

    # ── styles ────────────────────────────────────────────────────────────────
    def _style(self):
        s = ttk.Style(self); s.theme_use("clam")
        s.configure(".", background=BG, foreground=TEXT, font=FB)
        s.configure("Treeview", background=PANEL, foreground=TEXT,
                    fieldbackground=PANEL, rowheight=26, borderwidth=0, font=FL)
        s.configure("Treeview.Heading", background=CARD, foreground=TEXT,
                    font=("Segoe UI",9,"bold"), relief="flat")
        s.map("Treeview",
              background=[("selected",SEL_BG)], foreground=[("selected",TEXT)])
        s.map("Treeview.Heading", background=[("active",CARD)])
        for o in ("Vertical","Horizontal"):
            s.configure(f"{o}.TScrollbar", background=CARD, troughcolor=BG,
                        bordercolor=BG, arrowcolor=MUTED, gripcount=0)
        s.configure("TProgressbar", troughcolor=CARD, background=ACCENT2,
                    bordercolor=BG, lightcolor=ACCENT2, darkcolor=ACCENT2)

    # ── layout ────────────────────────────────────────────────────────────────
    def _build(self):
        # top bar
        top = tk.Frame(self, bg=PANEL, pady=8, padx=14,
                       highlightthickness=1, highlightbackground="#30363D")
        top.pack(fill="x")
        tk.Label(top, text="GEM Tender Logger", font=FT, bg=PANEL, fg=TEXT).pack(side="left")
        self.fy_lbl = tk.Label(top, text="", font=FL, bg=ACCENT2, fg=TEXT, padx=10, pady=3)
        self.fy_lbl.pack(side="right", padx=(6,0))

        # folder bar
        fbar = tk.Frame(self, bg=BG, pady=5, padx=14)
        fbar.pack(fill="x")
        tk.Label(fbar, text="Save to:", font=FL, bg=BG, fg=MUTED).pack(side="left")
        tk.Entry(fbar, textvariable=self.save_folder, bg=CARD, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=FL,
                 highlightthickness=1, highlightbackground="#30363D",
                 highlightcolor=ACCENT2, width=60).pack(side="left", padx=(6,4))
        self._btn(fbar, "Browse", self._browse, bg=CARD).pack(side="left")

        # paned: left = paste+log, right = table
        pane = tk.PanedWindow(self, orient="horizontal", bg=BG,
                              sashwidth=5, sashrelief="flat", handlesize=0)
        pane.pack(fill="both", expand=True, padx=10, pady=(4,0))

        # ── LEFT ─────────────────────────────────────────────────────────────
        left = tk.Frame(pane, bg=BG)
        pane.add(left, minsize=320, width=400)

        tk.Label(left, text="Paste GEM Tender Block(s)", font=("Segoe UI",9,"bold"),
                 bg=BG, fg=MUTED).pack(anchor="w", pady=(4,2))
        self.paste_txt = tk.Text(left, bg=CARD, fg=TEXT, insertbackground=TEXT,
                                 relief="flat", font=FH, height=12,
                                 highlightthickness=1, highlightbackground="#30363D",
                                 highlightcolor=ACCENT2, wrap="word", undo=True)
        self.paste_txt.pack(fill="x")
        tk.Label(left, text="Paste one or many blocks — each starting with BID NO:",
                 font=("Segoe UI",8), bg=BG, fg=TEXTSUB).pack(anchor="w", pady=(2,4))

        # progress
        self.progress = ttk.Progressbar(left, orient="horizontal",
                                        mode="determinate", length=200)
        self.progress.pack(fill="x", pady=(0,4))
        self.prog_lbl = tk.Label(left, text="", font=("Segoe UI",8),
                                 bg=BG, fg=TEXTSUB)
        self.prog_lbl.pack(anchor="w")

        # buttons
        btn_row = tk.Frame(left, bg=BG)
        btn_row.pack(fill="x", pady=(4,8))
        self._btn(btn_row, "  1. Parse Blocks  ", self._do_parse,
                  bg=ACCENT2, pad=10).pack(side="left")
        self._btn(btn_row, "  2. Fetch Details (Selenium)  ",
                  self._do_fetch_all, bg=ACCENT, pad=10).pack(side="left", padx=6)
        self._btn(btn_row, "Clear", lambda: self.paste_txt.delete("1.0","end"),
                  bg=CARD).pack(side="left")

        # log
        tk.Label(left, text="Log", font=("Segoe UI",9,"bold"),
                 bg=BG, fg=MUTED).pack(anchor="w", pady=(0,2))
        log_fr = tk.Frame(left, bg=CARD,
                          highlightthickness=1, highlightbackground="#30363D")
        log_fr.pack(fill="both", expand=True)
        self.log_txt = tk.Text(log_fr, bg=CARD, fg=TEXTSUB, relief="flat",
                               font=("Consolas",8), state="disabled", wrap="word",
                               highlightthickness=0)
        lsb = ttk.Scrollbar(log_fr, orient="vertical", command=self.log_txt.yview)
        self.log_txt.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y")
        self.log_txt.pack(fill="both", expand=True, padx=4, pady=4)
        for tag,col in [("ok",SUCCESS),("warn",WARN),("err",ERR),("info",ACCENT2)]:
            self.log_txt.tag_configure(tag, foreground=col)

        # ── RIGHT ────────────────────────────────────────────────────────────
        right = tk.Frame(pane, bg=BG)
        pane.add(right, minsize=500)

        hdr = tk.Frame(right, bg=BG)
        hdr.pack(fill="x", pady=(4,4))
        tk.Label(hdr, text="Parsed Tenders", font=("Segoe UI",9,"bold"),
                 bg=BG, fg=MUTED).pack(side="left")
        self.count_lbl = tk.Label(hdr, text="0 rows", font=FL, bg=BG, fg=TEXTSUB)
        self.count_lbl.pack(side="left", padx=8)

        self._btn(hdr,"Select All",   self._sel_all,    bg=CARD).pack(side="right",padx=2)
        self._btn(hdr,"Delete Selected", self._del_sel, bg=CARD, fg=ERR).pack(side="right",padx=2)
        self._btn(hdr,"  Fetch Selected (Selenium)  ",
                  self._do_fetch_sel, bg="#2D333B").pack(side="right",padx=2)
        self._btn(hdr,"  Save Selected to Excel  ",
                  self._save_selected, bg=ACCENT, pad=10).pack(side="right",padx=(6,2))

        # treeview
        tv_fr = tk.Frame(right, bg=BG)
        tv_fr.pack(fill="both", expand=True)
        cols = [c[0] for c in TV_COLS]
        self.tv = ttk.Treeview(tv_fr, columns=cols, show="headings",
                               selectmode="extended")
        for cid, lbl, w in TV_COLS:
            self.tv.heading(cid, text=lbl, command=lambda c=cid: self._sort(c))
            self.tv.column(cid, width=w, minwidth=40, stretch=False)

        vsb = ttk.Scrollbar(tv_fr, orient="vertical",   command=self.tv.yview)
        hsb = ttk.Scrollbar(tv_fr, orient="horizontal", command=self.tv.xview)
        self.tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tv_fr.rowconfigure(0, weight=1); tv_fr.columnconfigure(0, weight=1)

        self.tv.tag_configure("alt",     background="#1C2128")
        self.tv.tag_configure("fetched", background="#1A2E1A", foreground=SUCCESS)
        self.tv.tag_configure("saved",   background="#1A3A2A", foreground=SUCCESS)
        self.tv.tag_configure("fetching",background="#2A2A1A", foreground=WARN)

        self.tv.bind("<Double-1>", self._on_dbl)
        self.tv.bind("<Button-1>", self._cancel_edit)

        # status bar
        self.status = tk.Label(self, text="Ready", font=FL,
                               bg=PANEL, fg=MUTED, anchor="w", padx=10, pady=4)
        self.status.pack(fill="x", side="bottom")

    # ── widget helpers ────────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, bg=CARD, fg=TEXT, pad=6):
        return tk.Button(parent, text=text, command=cmd,
                         bg=bg, fg=fg, relief="flat", font=FL,
                         padx=pad, pady=4,
                         activebackground=ACCENT2, activeforeground=TEXT,
                         cursor="hand2")

    def _log(self, level, msg):
        self.log_txt.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_txt.insert("end", f"[{ts}] {msg}\n", level)
        self.log_txt.see("end")
        self.log_txt.configure(state="disabled")
        self.update_idletasks()

    def _set_status(self, msg, color=MUTED):
        self.status.configure(text=msg, fg=color)
        self.update_idletasks()

    def _set_prog(self, val, label=""):
        self.progress["value"] = val
        self.prog_lbl.configure(text=label)
        self.update_idletasks()

    def _fy_tick(self):
        self.fy_lbl.configure(text=f"FY {financial_year(datetime.now())}")
        self.after(60000, self._fy_tick)

    def _browse(self):
        d = filedialog.askdirectory(title="Select output folder",
                                    initialdir=self.save_folder.get())
        if d: self.save_folder.set(d)

    # ── Step 1 — parse paste blocks ───────────────────────────────────────────
    def _do_parse(self):
        raw = self.paste_txt.get("1.0","end").strip()
        if not raw: self._log("warn","Paste area is empty."); return
        self._log("info", f"--- Parse started {datetime.now().strftime('%H:%M:%S')} ---")
        self._set_prog(0,"Splitting blocks…")

        def worker():
            blocks = split_blocks(raw)
            total  = len(blocks)
            self._log("info", f"Found {total} block(s).")
            recs = []
            for i, blk in enumerate(blocks,1):
                rec = parse_one(blk)
                self._set_prog(int(i/total*100), f"Parsing {i}/{total}…")
                time.sleep(0.04)
                if rec.get("bid_no"):
                    recs.append(rec)
                    flds = [k for k,v in rec.items() if v]
                    self._log("ok", f"[{i}/{total}] {rec['bid_no']} — {len(flds)} fields")
                else:
                    self._log("warn", f"[{i}/{total}] SKIP — BID NO not found")
            self.after(0, lambda: self._add_rows(recs, total))
        threading.Thread(target=worker, daemon=True).start()

    def _add_rows(self, recs, total):
        for rec in recs:
            self._records.append(rec)
            self._tv_insert(rec)
        self._refresh_alt()
        self.count_lbl.configure(text=f"{len(self._records)} rows")
        skipped = total - len(recs)
        msg = f"Parsed {total} block(s): {len(recs)} added" + (f", {skipped} skipped" if skipped else "")
        self._log("info", msg)
        self._set_status(msg, SUCCESS if recs else WARN)
        self._set_prog(100, "Done.")
        if recs: self.paste_txt.delete("1.0","end")

    # ── Step 2 — Selenium fetch ───────────────────────────────────────────────
    def _do_fetch_all(self):
        """Fetch details for ALL records that have a bid_url."""
        targets = [(i, r) for i,r in enumerate(self._records) if r.get("bid_url")]
        self._run_fetch(targets, "all")

    def _do_fetch_sel(self):
        """Fetch details for SELECTED rows only."""
        sel = self.tv.selection()
        if not sel:
            self._log("warn","No rows selected."); return
        targets = []
        for iid in sel:
            idx = self.tv.index(iid)
            if idx < len(self._records) and self._records[idx].get("bid_url"):
                targets.append((idx, self._records[idx]))
        if not targets:
            self._log("warn","Selected rows have no Bid URL."); return
        self._run_fetch(targets, "selected")

    def _run_fetch(self, targets, label):
        if self._fetch_running:
            self._log("warn","A fetch is already running. Please wait."); return
        if not targets:
            self._log("warn","No rows with Bid URL to fetch."); return

        if not _try_import_selenium():
            messagebox.showerror("Missing library",
                "Please install Selenium:\n\npip install selenium webdriver-manager")
            return

        self._fetch_running = True
        self._log("info", f"--- Selenium fetch started: {len(targets)} {label} row(s) ---")
        self._set_prog(0, f"Fetching 0/{len(targets)}…")

        iid_map = {i: iid for i,iid in enumerate(self.tv.get_children())}

        def worker():
            total = len(targets)
            for n, (idx, rec) in enumerate(targets, 1):
                iid = iid_map.get(idx)
                bid = rec.get("bid_no","?")
                url = rec["bid_url"]

                self._set_prog(int((n-1)/total*100), f"Fetching {n}/{total}: {bid}")
                self._log("info", f"[{n}/{total}] Fetching {bid}")

                # mark row as "fetching"
                if iid: self.after(0, lambda i=iid: self.tv.item(i, tags=("fetching",)))

                extra = scrape_bid_page(url, log_fn=self._log)

                if extra:
                    rec.update(extra)
                    # update treeview cells
                    def update_tv(i=iid, r=rec):
                        if i:
                            for cid in TV_IDS:
                                if cid in r:
                                    self.tv.set(i, cid, r[cid])
                            self.tv.item(i, tags=("fetched",))
                    self.after(0, update_tv)
                    self._log("ok", f"[{n}/{total}] {bid} — merged {len(extra)} extra fields")
                else:
                    if iid: self.after(0, lambda i=iid: self.tv.item(i, tags=()))
                    self._log("warn", f"[{n}/{total}] {bid} — no extra data scraped")

                self._set_prog(int(n/total*100), f"Fetched {n}/{total}")

            self._fetch_running = False
            self._set_prog(100, "Fetch complete.")
            msg = f"Selenium fetch done: {total} URL(s) processed"
            self._log("info", f"--- {msg} ---")
            self.after(0, lambda: self._set_status(msg, SUCCESS))

        threading.Thread(target=worker, daemon=True).start()

    # ── table helpers ─────────────────────────────────────────────────────────
    def _tv_insert(self, rec):
        vals = tuple(rec.get(c,"") for c in TV_IDS)
        return self.tv.insert("","end", values=vals)

    def _refresh_alt(self):
        for i, iid in enumerate(self.tv.get_children()):
            cur_tags = self.tv.item(iid,"tags")
            special = [t for t in cur_tags if t in ("fetched","saved","fetching")]
            if not special:
                self.tv.item(iid, tags=("alt",) if i%2 else ())

    _sort_state = {}
    def _sort(self, col):
        rev = self._sort_state.get(col, False)
        items = [(self.tv.set(k,col),k) for k in self.tv.get_children()]
        items.sort(reverse=rev)
        for i,(_,k) in enumerate(items): self.tv.move(k,"",i)
        self._sort_state[col] = not rev
        self._refresh_alt()

    def _on_dbl(self, event):
        region = self.tv.identify_region(event.x, event.y)
        if region != "cell": return
        col = self.tv.identify_column(event.x)
        iid = self.tv.identify_row(event.y)
        if not iid: return
        col_idx = int(col[1:])-1
        if col_idx >= len(TV_IDS): return
        col_id = TV_IDS[col_idx]
        bbox = self.tv.bbox(iid, col)
        if not bbox: return
        x,y,w,h = bbox
        var = tk.StringVar(value=self.tv.set(iid, col_id))
        e = tk.Entry(self.tv, textvariable=var, bg=SEL_BG, fg=TEXT,
                     insertbackground=TEXT, relief="flat", font=FL,
                     highlightthickness=0)
        e.place(x=x,y=y,width=w,height=h); e.focus_set(); e.select_range(0,"end")
        self._editing = (iid, col_id, e)
        def commit(ev=None):
            nv = var.get(); self.tv.set(iid,col_id,nv)
            idx = self.tv.index(iid)
            if idx < len(self._records): self._records[idx][col_id]=nv
            e.destroy(); self._editing=None
        e.bind("<Return>",commit); e.bind("<Tab>",commit)
        e.bind("<Escape>",lambda ev: e.destroy())

    def _cancel_edit(self, event):
        if self._editing:
            try: self._editing[2].destroy()
            except: pass
            self._editing=None

    def _sel_all(self):
        self.tv.selection_set(self.tv.get_children())

    def _del_sel(self):
        sel = self.tv.selection()
        if not sel: return
        for iid in sorted(sel, key=self.tv.index, reverse=True):
            idx = self.tv.index(iid)
            self.tv.delete(iid)
            if idx < len(self._records): self._records.pop(idx)
        self._refresh_alt()
        self.count_lbl.configure(text=f"{len(self._records)} rows")
        self._log("info", f"Deleted {len(sel)} row(s).")

    def _save_selected(self):
        sel = self.tv.selection()
        if not sel:
            self._log("warn","No rows selected."); return
        folder = self.save_folder.get().strip()
        if not folder:
            self._set_status("Set output folder first.", ERR); return
        os.makedirs(folder, exist_ok=True)
        fy   = financial_year(datetime.now())
        path = xl_path(folder, fy)
        ensure_workbook(path)
        recs = []
        for iid in sel:
            idx = self.tv.index(iid)
            if idx < len(self._records): recs.append(self._records[idx])
        try:
            snos = xl_append(path, recs)
            msg = f"Saved {len(snos)} row(s) → {os.path.basename(path)}  (S.No {snos[0]}–{snos[-1]})"
            self._log("ok", msg); self._set_status(msg, SUCCESS); self._fy_tick()
            for iid in sel: self.tv.item(iid, tags=("saved",))
        except Exception as ex:
            self._log("err", f"Save error: {ex}")
            messagebox.showerror("Save Error", str(ex))
