"""
GEM Tender Logger — Desktop UI
--------------------------------
A Tkinter GUI for logging GEM tenders to a financial-year Excel file.

Requirements:
    pip install openpyxl
    (tkinter ships with Python on Windows/macOS; on Ubuntu: sudo apt install python3-tk)

Run:
    python gem_tender_ui.py
"""

import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── Excel logic (same as CLI script) ─────────────────────────────────────────

HEADERS = [
    "S.No", "Bid No", "Bid URL", "Items", "Quantity",
    "Department / Buyer", "Location", "Category",
    "Estimated Value (₹)", "Evaluation Method",
    "Start Date", "End Date", "Entry Date", "Remarks",
]

THIN        = Side(style="thin")
BORDER      = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HDR_FILL    = PatternFill("solid", start_color="1F4E79")
HDR_FONT    = Font(bold=True, color="FFFFFF", name="Arial", size=10)
DATA_FONT   = Font(name="Arial", size=10)
ALT_FILL    = PatternFill("solid", start_color="DCE6F1")
COL_WIDTHS  = [6, 22, 40, 30, 10, 35, 18, 22, 18, 22, 18, 18, 14, 22]


def financial_year(dt: datetime) -> str:
    if dt.month >= 4:
        return f"{dt.year}-{str(dt.year + 1)[-2:]}"
    return f"{dt.year - 1}-{str(dt.year)[-2:]}"


def excel_filename(folder: str, fy: str) -> str:
    return os.path.join(folder, f"GEM_Tenders_FY_{fy}.xlsx")


def create_workbook(path: str):
    wb = Workbook()
    ws = wb.active
    ws.title = "Tenders"
    ws.append(HEADERS)
    for col in range(1, len(HEADERS) + 1):
        c = ws.cell(row=1, column=col)
        c.font      = HDR_FONT
        c.fill      = HDR_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border    = BORDER
    ws.row_dimensions[1].height = 30
    for i, w in enumerate(COL_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    wb.save(path)


def append_row(path: str, row_data: list) -> int:
    wb = load_workbook(path)
    ws = wb["Tenders"]
    next_row = ws.max_row + 1
    sno = next_row - 1
    row_data[0] = sno
    ws.append(row_data)
    alt = sno % 2 == 0
    for col in range(1, len(HEADERS) + 1):
        c = ws.cell(row=next_row, column=col)
        c.font      = DATA_FONT
        c.border    = BORDER
        c.alignment = Alignment(vertical="center", wrap_text=True)
        if alt:
            c.fill = ALT_FILL
    ws.row_dimensions[next_row].height = 20
    wb.save(path)
    return sno


def parse_bid_line(line: str):
    m = re.search(r"\[([^\]]+)\]\((https?://[^)]+)\)", line)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    plain = re.sub(r"BID\s*NO\s*:\s*", "", line, flags=re.IGNORECASE).strip()
    return plain, ""


# ── GUI ───────────────────────────────────────────────────────────────────────

DARK_BG   = "#0F1923"
CARD_BG   = "#1A2535"
ACCENT    = "#2563EB"
ACCENT_H  = "#1D4ED8"
MUTED     = "#94A3B8"
TEXT      = "#F1F5F9"
ENTRY_BG  = "#0F1923"
ENTRY_BD  = "#334155"
SUCCESS   = "#22C55E"
ERROR_COL = "#EF4444"
WARN      = "#F59E0B"
FONT_BODY = ("Segoe UI", 10)
FONT_LBL  = ("Segoe UI", 9)
FONT_HEAD = ("Segoe UI", 13, "bold")
FONT_SUB  = ("Segoe UI", 9)


class TenderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GEM Tender Logger")
        self.configure(bg=DARK_BG)
        self.resizable(True, True)
        self.minsize(680, 640)

        # output folder
        self.save_folder = tk.StringVar(value=os.path.expanduser("~\\Documents")
                                        if os.name == "nt" else os.path.expanduser("~/Documents"))

        self._build_ui()
        self.update_fy_label()

    # ── layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── top bar ──────────────────────────────────────────────────────────
        top = tk.Frame(self, bg=ACCENT, pady=10, padx=18)
        top.pack(fill="x")
        tk.Label(top, text="🏛  GEM Tender Logger", font=FONT_HEAD,
                 bg=ACCENT, fg=TEXT).pack(side="left")
        self.fy_badge = tk.Label(top, text="", font=FONT_SUB,
                                 bg="#1E40AF", fg=TEXT, padx=8, pady=3)
        self.fy_badge.pack(side="right")

        # ── scrollable body ───────────────────────────────────────────────────
        outer = tk.Frame(self, bg=DARK_BG)
        outer.pack(fill="both", expand=True, padx=16, pady=12)

        canvas = tk.Canvas(outer, bg=DARK_BG, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.form_frame = tk.Frame(canvas, bg=DARK_BG)
        self._win = canvas.create_window((0, 0), window=self.form_frame, anchor="nw")

        self.form_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(self._win, width=e.width))
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._build_form(self.form_frame)

    def _section(self, parent, title):
        f = tk.Frame(parent, bg=CARD_BG, bd=0)
        f.pack(fill="x", pady=(0, 10))
        tk.Label(f, text=title, font=("Segoe UI", 9, "bold"),
                 bg=CARD_BG, fg=ACCENT, padx=12, pady=7).pack(anchor="w")
        ttk.Separator(f, orient="horizontal").pack(fill="x", padx=12)
        inner = tk.Frame(f, bg=CARD_BG, padx=12, pady=8)
        inner.pack(fill="x")
        return inner

    def _row(self, parent, label, widget_fn, colspan=1, note=None):
        r = tk.Frame(parent, bg=CARD_BG)
        r.pack(fill="x", pady=3)
        lbl_txt = label + ("  *" if note == "req" else "")
        tk.Label(r, text=lbl_txt, font=FONT_LBL, bg=CARD_BG,
                 fg=MUTED if note != "req" else TEXT, width=22, anchor="w").pack(side="left")
        w = widget_fn(r)
        w.pack(side="left", fill="x", expand=True)
        return w

    def _entry(self, parent, var=None, **kw):
        e = tk.Entry(parent, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                     relief="flat", font=FONT_BODY, bd=0,
                     highlightthickness=1, highlightbackground=ENTRY_BD,
                     highlightcolor=ACCENT, textvariable=var, **kw)
        return e

    def _build_form(self, parent):
        self.vars = {}

        # ── Bid Details ───────────────────────────────────────────────────────
        s1 = self._section(parent, "BID DETAILS")

        # smart paste field
        paste_row = tk.Frame(s1, bg=CARD_BG)
        paste_row.pack(fill="x", pady=(0, 6))
        tk.Label(paste_row, text="Smart Paste", font=FONT_LBL,
                 bg=CARD_BG, fg=MUTED, width=22, anchor="w").pack(side="left")
        self.paste_var = tk.StringVar()
        pe = self._entry(paste_row, var=self.paste_var)
        pe.pack(side="left", fill="x", expand=True)
        tk.Button(paste_row, text="Parse →", font=FONT_LBL,
                  bg=ACCENT, fg=TEXT, relief="flat", padx=8,
                  activebackground=ACCENT_H, activeforeground=TEXT,
                  cursor="hand2", command=self._smart_parse
                  ).pack(side="left", padx=(6, 0))
        tk.Label(s1, text="Paste the full 'BID NO: [...](...) line above and click Parse →",
                 font=("Segoe UI", 8), bg=CARD_BG, fg="#475569").pack(anchor="w", pady=(0, 4))

        ttk.Separator(s1, orient="horizontal").pack(fill="x", pady=4)

        for key, lbl, req in [
            ("bid_no",  "Bid No  *",  True),
            ("bid_url", "Bid URL",    False),
        ]:
            self.vars[key] = tk.StringVar()
            self._row(s1, lbl, lambda p, v=self.vars[key]: self._entry(p, var=v),
                      note="req" if req else None)

        # ── Item Details ──────────────────────────────────────────────────────
        s2 = self._section(parent, "ITEM DETAILS")
        for key, lbl in [("items", "Items"), ("quantity", "Quantity")]:
            self.vars[key] = tk.StringVar()
            self._row(s2, lbl, lambda p, v=self.vars[key]: self._entry(p, var=v))

        # ── Buyer / Organisation ──────────────────────────────────────────────
        s3 = self._section(parent, "BUYER & ORGANISATION")
        for key, lbl, req in [
            ("dept",     "Dept / Buyer  *", True),
            ("location", "Location",        False),
            ("category", "Category",        False),
        ]:
            self.vars[key] = tk.StringVar()
            self._row(s3, lbl, lambda p, v=self.vars[key]: self._entry(p, var=v),
                      note="req" if req else None)

        # ── Financial ─────────────────────────────────────────────────────────
        s4 = self._section(parent, "FINANCIAL")
        for key, lbl in [("est_value", "Est. Value (₹)"), ("eval_method", "Evaluation Method")]:
            self.vars[key] = tk.StringVar()
            self._row(s4, lbl, lambda p, v=self.vars[key]: self._entry(p, var=v))

        # ── Dates ─────────────────────────────────────────────────────────────
        s5 = self._section(parent, "DATES")
        for key, lbl in [("start_date", "Start Date"), ("end_date", "End Date")]:
            self.vars[key] = tk.StringVar()
            r = tk.Frame(s5, bg=CARD_BG)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=lbl, font=FONT_LBL, bg=CARD_BG,
                     fg=MUTED, width=22, anchor="w").pack(side="left")
            e = self._entry(r, var=self.vars[key])
            e.pack(side="left", fill="x", expand=True)
            tk.Label(r, text="DD-MM-YYYY HH:MM", font=("Segoe UI", 8),
                     bg=CARD_BG, fg="#475569", padx=6).pack(side="left")

        # ── Remarks ───────────────────────────────────────────────────────────
        s6 = self._section(parent, "REMARKS")
        rr = tk.Frame(s6, bg=CARD_BG)
        rr.pack(fill="x", pady=3)
        tk.Label(rr, text="Remarks", font=FONT_LBL, bg=CARD_BG,
                 fg=MUTED, width=22, anchor="w").pack(side="left", anchor="n", pady=2)
        self.remarks_txt = tk.Text(rr, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                                   relief="flat", font=FONT_BODY, height=3,
                                   highlightthickness=1, highlightbackground=ENTRY_BD,
                                   highlightcolor=ACCENT)
        self.remarks_txt.pack(side="left", fill="x", expand=True)

        # ── Save location ─────────────────────────────────────────────────────
        s7 = self._section(parent, "SAVE LOCATION")
        fr = tk.Frame(s7, bg=CARD_BG)
        fr.pack(fill="x", pady=3)
        tk.Label(fr, text="Output Folder", font=FONT_LBL,
                 bg=CARD_BG, fg=MUTED, width=22, anchor="w").pack(side="left")
        self._entry(fr, var=self.save_folder).pack(side="left", fill="x", expand=True)
        tk.Button(fr, text="Browse…", font=FONT_LBL,
                  bg="#334155", fg=TEXT, relief="flat", padx=8,
                  activebackground="#475569", activeforeground=TEXT,
                  cursor="hand2", command=self._browse).pack(side="left", padx=(6, 0))

        # ── status + buttons ──────────────────────────────────────────────────
        bot = tk.Frame(parent, bg=DARK_BG)
        bot.pack(fill="x", pady=(4, 0))

        self.status_lbl = tk.Label(bot, text="", font=FONT_SUB,
                                   bg=DARK_BG, fg=MUTED)
        self.status_lbl.pack(side="left", padx=4)

        tk.Button(bot, text="Clear Form", font=FONT_BODY,
                  bg="#334155", fg=TEXT, relief="flat", padx=14, pady=8,
                  activebackground="#475569", activeforeground=TEXT,
                  cursor="hand2", command=self._clear
                  ).pack(side="right", padx=(6, 0))

        tk.Button(bot, text="  💾  Save to Excel  ", font=("Segoe UI", 11, "bold"),
                  bg=ACCENT, fg=TEXT, relief="flat", padx=18, pady=8,
                  activebackground=ACCENT_H, activeforeground=TEXT,
                  cursor="hand2", command=self._save
                  ).pack(side="right")

    # ── helpers ───────────────────────────────────────────────────────────────

    def update_fy_label(self):
        fy = financial_year(datetime.now())
        self.fy_badge.config(text=f"FY {fy}")

    def _smart_parse(self):
        raw = self.paste_var.get().strip()
        if not raw:
            return
        bid_no, bid_url = parse_bid_line(raw)
        self.vars["bid_no"].set(bid_no)
        if bid_url:
            self.vars["bid_url"].set(bid_url)
        self.paste_var.set("")
        self._status(f"Parsed: {bid_no}", SUCCESS)

    def _browse(self):
        folder = filedialog.askdirectory(title="Select output folder",
                                         initialdir=self.save_folder.get())
        if folder:
            self.save_folder.set(folder)

    def _status(self, msg, color=MUTED):
        self.status_lbl.config(text=msg, fg=color)

    def _clear(self):
        for v in self.vars.values():
            v.set("")
        self.remarks_txt.delete("1.0", "end")
        self.paste_var.set("")
        self._status("Form cleared.", MUTED)

    def _save(self):
        # validation
        if not self.vars["bid_no"].get().strip():
            self._status("⚠  Bid No is required.", ERROR_COL)
            return
        if not self.vars["dept"].get().strip():
            self._status("⚠  Department / Buyer is required.", ERROR_COL)
            return

        folder = self.save_folder.get().strip()
        if not folder:
            self._status("⚠  Please set an output folder.", ERROR_COL)
            return
        os.makedirs(folder, exist_ok=True)

        now  = datetime.now()
        fy   = financial_year(now)
        path = excel_filename(folder, fy)

        if not os.path.exists(path):
            create_workbook(path)

        row = [
            0,
            self.vars["bid_no"].get().strip(),
            self.vars["bid_url"].get().strip(),
            self.vars["items"].get().strip(),
            self.vars["quantity"].get().strip(),
            self.vars["dept"].get().strip(),
            self.vars["location"].get().strip(),
            self.vars["category"].get().strip(),
            self.vars["est_value"].get().strip(),
            self.vars["eval_method"].get().strip(),
            self.vars["start_date"].get().strip(),
            self.vars["end_date"].get().strip(),
            now.strftime("%d-%m-%Y %H:%M"),
            self.remarks_txt.get("1.0", "end").strip(),
        ]

        try:
            sno = append_row(path, row)
            self._status(f"✔  Saved S.No {sno} → {os.path.basename(path)}", SUCCESS)
            self.update_fy_label()
            if messagebox.askyesno("Saved", f"Entry #{sno} saved to:\n{path}\n\nClear form for next entry?"):
                self._clear()
        except Exception as ex:
            self._status(f"✘  Error: {ex}", ERROR_COL)
            messagebox.showerror("Save Error", str(ex))


# ── run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = TenderApp()

    # style scrollbar
    style = ttk.Style(app)
    style.theme_use("clam")
    style.configure("Vertical.TScrollbar",
                    background="#334155", troughcolor=DARK_BG,
                    bordercolor=DARK_BG, arrowcolor=MUTED)

    app.mainloop()
