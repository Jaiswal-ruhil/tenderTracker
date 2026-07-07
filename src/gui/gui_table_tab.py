import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import re
from datetime import datetime, date, timedelta
import calendar

# Local imports
from config import (
    BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN, SEL_BG,
    FL, FB, FT, TV_COLS, TV_IDS
)
from excel import financial_year, xl_path, ensure_workbook, xl_append
import db
from vector_search import semantic_search

class DatePickerPopup(tk.Toplevel):
    def __init__(self, parent, entry_var, x, y):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=PANEL, highlightthickness=1, highlightbackground="#30363D")
        self.entry_var = entry_var
        self.geometry(f"240x240+{x}+{y}")
        
        # Focus/Grab handling
        self.grab_set()
        
        self.year = datetime.now().year
        self.month = datetime.now().month
        
        # Initialize to entry value if valid
        try:
            curr_val = entry_var.get().strip()
            m = re.search(r"\b([0-9]{1,2})[-/]([0-9]{1,2})[-/]([0-9]{4})\b", curr_val)
            if m:
                d, m_val, y = map(int, m.groups())
                self.year = y
                self.month = m_val
            else:
                m2 = re.search(r"\b([0-9]{4})[-/]([0-9]{1,2})[-/]([0-9]{1,2})\b", curr_val)
                if m2:
                    y, m_val, d = map(int, m2.groups())
                    self.year = y
                    self.month = m_val
        except Exception:
            pass
            
        self.header_fr = tk.Frame(self, bg=PANEL)
        self.header_fr.pack(fill="x", pady=4)
        
        btn_prev = tk.Button(self.header_fr, text="<", command=self.prev_month,
                             bg=CARD, fg=TEXT, relief="flat", font=("Segoe UI", 9, "bold"),
                             padx=6, pady=2, activebackground=ACCENT, activeforeground=BG, cursor="hand2")
        btn_prev.pack(side="left", padx=6)
        
        self.title_lbl = tk.Label(self.header_fr, text="", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=TEXT)
        self.title_lbl.pack(side="left", fill="x", expand=True)
        
        btn_next = tk.Button(self.header_fr, text=">", command=self.next_month,
                             bg=CARD, fg=TEXT, relief="flat", font=("Segoe UI", 9, "bold"),
                             padx=6, pady=2, activebackground=ACCENT, activeforeground=BG, cursor="hand2")
        btn_next.pack(side="right", padx=6)
        
        days_fr = tk.Frame(self, bg=PANEL)
        days_fr.pack(fill="x")
        for d in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
            lbl = tk.Label(days_fr, text=d, font=("Segoe UI", 8, "bold"), bg=PANEL, fg=MUTED, width=3)
            lbl.pack(side="left", fill="x", expand=True)
            
        self.grid_fr = tk.Frame(self, bg=PANEL)
        self.grid_fr.pack(fill="both", expand=True, pady=4)
        
        self.bind("<Button-1>", self._check_click_outside)
        
        self.draw_grid()

    def prev_month(self):
        if self.month == 1:
            self.month = 12
            self.year -= 1
        else:
            self.month -= 1
        self.draw_grid()
        
    def next_month(self):
        if self.month == 12:
            self.month = 1
            self.year += 1
        else:
            self.month += 1
        self.draw_grid()

    def draw_grid(self):
        for widget in self.grid_fr.winfo_children():
            widget.destroy()
            
        self.title_lbl.configure(text=f"{calendar.month_name[self.month]} {self.year}")
        
        cal = calendar.Calendar()
        try:
            weeks = cal.monthdayscalendar(self.year, self.month)
        except Exception:
            weeks = []
            
        for r_idx, week in enumerate(weeks):
            w_frame = tk.Frame(self.grid_fr, bg=PANEL)
            w_frame.pack(fill="x")
            for c_idx, day in enumerate(week):
                if day == 0:
                    lbl = tk.Label(w_frame, text="", bg=PANEL, width=3)
                    lbl.pack(side="left", fill="x", expand=True)
                else:
                    btn = tk.Button(w_frame, text=str(day),
                                    command=lambda d=day: self.select_date(d),
                                    bg=CARD, fg=TEXT, relief="flat",
                                    font=("Segoe UI", 8), width=3,
                                    activebackground=ACCENT, activeforeground=BG, cursor="hand2")
                    if self.year == datetime.now().year and self.month == datetime.now().month and day == datetime.now().day:
                        btn.configure(fg=ACCENT, font=("Segoe UI", 8, "bold"))
                    btn.pack(side="left", fill="x", expand=True, padx=1, pady=1)

    def select_date(self, day):
        formatted_date = f"{day:02d}-{self.month:02d}-{self.year}"
        self.entry_var.set(formatted_date)
        self.destroy()

    def _check_click_outside(self, event):
        x, y = event.x_root, event.y_root
        w_x = self.winfo_rootx()
        w_y = self.winfo_rooty()
        w_w = self.winfo_width()
        w_h = self.winfo_height()
        if not (w_x <= x <= w_x + w_w and w_y <= y <= w_y + w_h):
            self.destroy()


class TreeviewHover:
    """
    Hover row highlight effect for ttk.Treeview.
    Dynamically applies a 'hover' tag to the row currently under the mouse cursor.
    """
    def __init__(self, treeview):
        self.tv = treeview
        self.last_hovered_iid = None
        self.tv.tag_configure("hover", background="#26303C")  # Elegant dark slate gray for hover
        self.tv.bind("<Motion>", self._on_motion, add="+")
        self.tv.bind("<Leave>", self._on_leave, add="+")

    def _on_motion(self, event):
        iid = self.tv.identify_row(event.y)
        if iid != self.last_hovered_iid:
            if self.last_hovered_iid:
                self._remove_hover(self.last_hovered_iid)
            if iid:
                self._add_hover(iid)
                self.last_hovered_iid = iid
            else:
                self.last_hovered_iid = None

    def _on_leave(self, event):
        if self.last_hovered_iid:
            self._remove_hover(self.last_hovered_iid)
            self.last_hovered_iid = None

    def _add_hover(self, iid):
        try:
            tags = list(self.tv.item(iid, "tags"))
            if "hover" not in tags:
                tags.append("hover")
                self.tv.item(iid, tags=tuple(tags))
        except Exception:
            pass

    def _remove_hover(self, iid):
        try:
            tags = list(self.tv.item(iid, "tags"))
            if "hover" in tags:
                tags.remove("hover")
                self.tv.item(iid, tags=tuple(tags))
        except Exception:
            pass


class CellTooltip:
    """
    Hover tooltip for ttk.Treeview cells.
    Since Treeview doesn't support native multi-line rendering, this tooltip
    shows the full wrapped cell content when the user hovers over a cell.
    Only appears when the cell text is long enough to be truncated.
    """
    MIN_CHARS = 20          # don't show tooltip for very short values
    WRAP_CHARS = 80         # wrap at this many characters per line
    DELAY_MS  = 500         # ms before tooltip appears
    MAX_LINES = 12          # cap how many lines to show

    def __init__(self, treeview, tv_ids):
        self.tv     = treeview
        self.tv_ids = tv_ids
        self._tip   = None
        self._job   = None

        treeview.bind("<Motion>",   self._on_motion,  add="+")
        treeview.bind("<Leave>",    self._hide,        add="+")
        treeview.bind("<Button-1>", self._hide,        add="+")
        treeview.bind("<Button-3>", self._hide,        add="+")

    def _on_motion(self, event):
        col = self.tv.identify_column(event.x)
        iid = self.tv.identify_row(event.y)
        if not col or not iid:
            self._hide()
            return

        col_idx = int(col[1:]) - 1
        if col_idx < 0 or col_idx >= len(self.tv_ids):
            self._hide()
            return

        col_id  = self.tv_ids[col_idx]
        cell_val = self.tv.set(iid, col_id)
        if not cell_val or len(str(cell_val)) < self.MIN_CHARS:
            self._hide()
            return

        # Cancel pending tooltip if the cell changed
        if self._job:
            self.tv.after_cancel(self._job)
        self._hide_tip()

        x_root = event.x_root + 12
        y_root = event.y_root + 16
        self._job = self.tv.after(
            self.DELAY_MS,
            lambda: self._show(cell_val, col_id, x_root, y_root)
        )

    def _show(self, text, col_id, x, y):
        import textwrap
        self._job = None
        self._hide_tip()

        # Word-wrap the text
        wrapped = textwrap.fill(str(text), width=self.WRAP_CHARS)
        lines = wrapped.splitlines()
        if len(lines) > self.MAX_LINES:
            lines = lines[:self.MAX_LINES]
            lines.append("…")
        display = "\n".join(lines)

        self._tip = tk.Toplevel(self.tv)
        self._tip.overrideredirect(True)
        self._tip.attributes("-topmost", True)
        self._tip.configure(bg="#2D333B", highlightthickness=1,
                            highlightbackground="#444C56")

        # Column label header
        lbl_header = tk.Label(self._tip,
                              text=col_id.replace("_", " ").title(),
                              bg="#2D333B", fg="#8B949E",
                              font=("Segoe UI", 8, "bold"),
                              anchor="w", padx=8, pady=2)
        lbl_header.pack(fill="x")

        sep = tk.Frame(self._tip, bg="#444C56", height=1)
        sep.pack(fill="x")

        lbl = tk.Label(self._tip,
                       text=display,
                       justify="left",
                       anchor="nw",
                       bg="#1C2128", fg="#E6EDF3",
                       font=("Segoe UI", 9),
                       wraplength=560,
                       padx=10, pady=6)
        lbl.pack(fill="both", expand=True)

        # Clamp to screen
        self._tip.update_idletasks()
        sw = self._tip.winfo_screenwidth()
        sh = self._tip.winfo_screenheight()
        tw = self._tip.winfo_width()
        th = self._tip.winfo_height()
        if x + tw > sw:
            x = sw - tw - 8
        if y + th > sh:
            y = y - th - 20

        self._tip.geometry(f"+{x}+{y}")

    def _hide_tip(self):
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

    def _hide(self, event=None):
        if self._job:
            self.tv.after_cancel(self._job)
            self._job = None
        self._hide_tip()


class TableTabMixin:
    def _build_table_tab(self):
        # Table Tab Header (formerly right header)
        hdr = tk.Frame(self.tab_table, bg=BG)
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

        # ── Filter & Refine Bar ──────────────────────────────────────────────
        filter_fr = tk.Frame(self.tab_table, bg=PANEL, padx=10, pady=6,
                             highlightthickness=1, highlightbackground="#30363D")
        filter_fr.pack(fill="x", pady=(0, 6))

        # Search box
        tk.Label(filter_fr, text="Search:", font=FL, bg=PANEL, fg=MUTED).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._refresh_table_view())
        
        self.search_ent = tk.Entry(filter_fr, textvariable=self.search_var, bg=CARD, fg=TEXT,
                              insertbackground=TEXT, relief="flat", font=FL, width=22,
                              highlightthickness=1, highlightbackground="#30363D",
                              highlightcolor=ACCENT2)
        self.search_ent.pack(side="left", padx=(4, 15))

        # Semantic Search Checkbox
        self.semantic_search_var = tk.BooleanVar(value=False)
        self.semantic_search_cb = tk.Checkbutton(
            filter_fr, text="Semantic Search", variable=self.semantic_search_var,
            bg=PANEL, fg=TEXT, selectcolor=CARD, activebackground=PANEL, activeforeground=TEXT,
            font=FL, command=self._refresh_table_view
        )
        self.semantic_search_cb.pack(side="left", padx=(0, 15))

        # View dropdown
        tk.Label(filter_fr, text="Filter:", font=FL, bg=PANEL, fg=MUTED).pack(side="left")
        
        self.view_var = tk.StringVar(value="Wants (Matches)")
        view_opt = ttk.Combobox(filter_fr, textvariable=self.view_var, 
                                values=["All Tenders", "Wants (Matches)", "Don't Wants (Filtered)"],
                                state="readonly", font=FL, width=20)
        view_opt.pack(side="left", padx=4)
        view_opt.bind("<<ComboboxSelected>>", lambda e: self._refresh_table_view())

        # Visual separator
        tk.Label(filter_fr, text="│", font=FL, bg=PANEL, fg="#30363D").pack(side="left", padx=(6, 6))

        # Status View dropdown
        tk.Label(filter_fr, text="Status:", font=FL, bg=PANEL, fg=MUTED).pack(side="left")
        self.status_view_var = tk.StringVar(value="All")
        status_view_opt = ttk.Combobox(filter_fr, textvariable=self.status_view_var,
                                       values=["All", "To Be Filed", "Evaluating", "Filed"],
                                       state="readonly", font=FL, width=13)
        status_view_opt.pack(side="left", padx=4)
        status_view_opt.bind("<<ComboboxSelected>>", lambda e: self._refresh_table_view())
        
        # Date Filter in Table View
        tk.Label(filter_fr, text="Date Filter:", font=FL, bg=PANEL, fg=MUTED).pack(side="left", padx=(10, 0))
        self.date_filter_type_var = tk.StringVar(value="None")
        self.date_filter_preset_var = tk.StringVar(value="All Dates")
        
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
        self.date_filter_combo.bind("<<ComboboxSelected>>", lambda e: self._on_date_combo_changed())

        # Custom date range entry frame (hidden by default)
        self.custom_date_frame = tk.Frame(filter_fr, bg=PANEL)
        
        tk.Label(self.custom_date_frame, text="From:", font=FL, bg=PANEL, fg=MUTED).pack(side="left", padx=(4, 2))
        self.date_from_var = tk.StringVar()
        self.date_from_var.trace_add("write", lambda *args: self._refresh_table_view())
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
        self.date_to_var = tk.StringVar()
        self.date_to_var.trace_add("write", lambda *args: self._refresh_table_view())
        self.date_to_ent = tk.Entry(self.custom_date_frame, textvariable=self.date_to_var, bg=CARD, fg=TEXT,
                                    insertbackground=TEXT, relief="flat", font=FL, width=10,
                                    highlightthickness=1, highlightbackground="#30363D")
        self.date_to_ent.pack(side="left")

        self.btn_to_cal = tk.Button(self.custom_date_frame, text="📅", bg=CARD, fg=TEXT, relief="flat",
                                    font=("Segoe UI", 9), padx=4, pady=0, cursor="hand2",
                                    activebackground=ACCENT)
        self.btn_to_cal.pack(side="left", padx=(2, 6))
        self.btn_to_cal.configure(command=lambda: self._show_datepicker(self.btn_to_cal, self.date_to_var))

        # Initialize default preset values for End Date filtering
        self._apply_date_filter_preset(initial=True)
        


        # Refine rules and copy table buttons
        self._btn(filter_fr, "⚙ Refine Rules...", self._show_filter_rules_dialog, bg=CARD).pack(side="right")
        self._btn(filter_fr, "👁 Select Columns...", self._show_column_selector, bg=CARD).pack(side="right", padx=(0, 6))
        self._btn(filter_fr, "📋 Copy Table", self._copy_table_output, bg=CARD).pack(side="right", padx=(0, 6))

        # Create a PanedWindow inside self.tab_table for resizable Treeview and Detail Side-Panel
        table_pane = tk.PanedWindow(self.tab_table, orient="horizontal", bg=BG,
                                    sashwidth=4, sashrelief="flat", handlesize=0)
        table_pane.pack(fill="both", expand=True)

        # treeview frame (placed in the left pane of table_pane)
        tv_fr = tk.Frame(table_pane, bg=BG)
        table_pane.add(tv_fr, minsize=400, stretch="always")

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

        # Detail Side-Panel frame (placed in the right pane of table_pane)
        self.detail_panel = tk.Frame(table_pane, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=12, pady=10)
        table_pane.add(self.detail_panel, minsize=320, stretch="always")

        # Detail Title
        detail_title = tk.Label(self.detail_panel, text="TENDER DETAILS", font=FT, bg=PANEL, fg=TEXT)
        detail_title.pack(anchor="w", pady=(0, 6))

        # PDF Control Frame
        self.pdf_frame = tk.Frame(self.detail_panel, bg=PANEL)
        self.pdf_frame.pack(fill="x", pady=(0, 8))
        
        self.pdf_lbl = tk.Label(self.pdf_frame, text="PDF: Not Linked", font=FL, bg=PANEL, fg=TEXTSUB, anchor="w")
        self.pdf_lbl.pack(side="left", fill="x", expand=True)
        
        self.btn_open_pdf = self._btn(self.pdf_frame, "📄 Open", self._open_associated_pdf, bg=CARD)
        self.btn_open_pdf.pack(side="right", padx=2)
        
        self.btn_link_pdf = self._btn(self.pdf_frame, "🔗 Link", self._link_associated_pdf, bg=CARD)
        self.btn_link_pdf.pack(side="right", padx=2)
        
        self.btn_unlink_pdf = self._btn(self.pdf_frame, "❌", self._unlink_associated_pdf, bg=CARD)
        self.btn_unlink_pdf.pack(side="right", padx=2)

        # Detail Scrollable Text widget
        txt_fr = tk.Frame(self.detail_panel, bg=PANEL)
        txt_fr.pack(fill="both", expand=True)

        self.detail_txt = tk.Text(txt_fr, bg=CARD, fg=TEXT, insertbackground=TEXT,
                                  relief="flat", font=FL, wrap="word", highlightthickness=0,
                                  padx=12, pady=12)
        self.detail_txt.pack(side="left", fill="both", expand=True)

        detail_vsb = ttk.Scrollbar(txt_fr, orient="vertical", command=self.detail_txt.yview)
        detail_vsb.pack(side="right", fill="y")
        self.detail_txt.configure(yscrollcommand=detail_vsb.set)
        
        # Configure tags for detail_txt formatting & highlighting
        self.detail_txt.tag_configure("header", foreground=ACCENT2, font=("Segoe UI", 10, "bold"))
        self.detail_txt.tag_configure("label", foreground=MUTED, font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("value", foreground=TEXT, font=("Segoe UI", 9))
        self.detail_txt.tag_configure("match_inc", background="#1A4A2A", foreground=SUCCESS, font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("match_exc", background="#4A1A1A", foreground=ERR, font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("match_search", background="#0A4D8C", foreground="#FFFFFF", font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("match_firm_inc", background="#0A3C5C", foreground="#84D2FF", font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("match_firm_loc", background="#2D1C4C", foreground="#C09EFF", font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("match_firm_exc", background="#4A1A1A", foreground=ERR, font=("Segoe UI", 9, "bold"))

        # Initialize detail text state
        self._clear_detail_panel()

        # Bind MouseWheel events for self.detail_txt
        def on_detail_mousewheel(event):
            if event.num == 5 or event.delta < 0:
                self.detail_txt.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                self.detail_txt.yview_scroll(-1, "units")
        self.detail_txt.bind("<MouseWheel>", on_detail_mousewheel)
        self.detail_txt.bind("<Button-4>", on_detail_mousewheel)
        self.detail_txt.bind("<Button-5>", on_detail_mousewheel)

        self.tv.tag_configure("alt",     background="#1C2128")
        self.tv.tag_configure("fetched", background="#1A2E1A", foreground=SUCCESS)
        self.tv.tag_configure("saved",   background="#1A3A2A", foreground=SUCCESS)
        self.tv.tag_configure("fetching",background="#2A2A1A", foreground=WARN)
        self.tv.tag_configure("dont_want", foreground="#5D6570")
        self.tv.tag_configure("manual_want", background="#1A3324")

        self.tv.bind("<Double-1>", self._on_dbl)
        self.tv.bind("<Button-1>", self._cancel_edit)
        self.tv.bind("<<TreeviewSelect>>", self._on_treeview_select)

        # Attach hover tooltip for full cell text (text-wrap workaround for Treeview)
        self._cell_tooltip = CellTooltip(self.tv, TV_IDS)
        self._treeview_hover = TreeviewHover(self.tv)

        # Context Menu
        self.ctx_menu = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, 
                                activebackground=SEL_BG, activeforeground=TEXT, font=FL)
        self.ctx_menu.add_command(label="Mark as Want (Keep)", command=self._mark_selected_want)
        self.ctx_menu.add_command(label="Mark as Don't Want (Ignore)", command=self._mark_selected_dont_want)
        self.ctx_menu.add_command(label="Reset Manual Tag", command=self._reset_selected_tag)
        self.ctx_menu.add_command(label="Manage Tags...", command=self._show_tags_dialog)
        
        # Submenu for Filing Status
        self.status_menu = tk.Menu(self.ctx_menu, tearoff=0, bg=PANEL, fg=TEXT,
                                   activebackground=SEL_BG, activeforeground=TEXT, font=FL)
        self.status_menu.add_command(label="To Be Filed", command=lambda: self._set_selected_filing_status("To Be Filed"))
        self.status_menu.add_command(label="Evaluating", command=lambda: self._set_selected_filing_status("Evaluating"))
        self.status_menu.add_command(label="Filed", command=lambda: self._set_selected_filing_status("Filed"))
        self.ctx_menu.add_cascade(label="Set Filing Status", menu=self.status_menu)
        
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="Link PDF File...", command=self._link_associated_pdf)
        self.ctx_menu.add_command(label="Open Associated PDF", command=self._open_associated_pdf)
        self.ctx_menu.add_command(label="Unlink PDF File", command=self._unlink_associated_pdf)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="Delete Selected", command=self._del_sel)
        self.ctx_menu.add_command(label="Fetch Details (Selenium)", command=self._do_fetch_sel)
        self.ctx_menu.add_command(label="Save Selected to Excel", command=self._save_selected)
        
        self.tv.bind("<Button-3>", self._show_context_menu)
        self.tv.bind("<Button-2>", self._show_context_menu) # For macOS
        self._apply_column_visibility()

    def _tv_insert(self, rec):
        raw_vals = []
        for c in TV_IDS:
            val = rec.get(c, "")
            if c == "tags" and isinstance(val, list):
                val = ", ".join(val)
            raw_vals.append(val)
        vals = tuple(raw_vals)
        tags = []
        
        # Wants / Don't Wants tags
        manual_want = rec.get("is_want")
        derived_want = rec.get("is_want_derived", True)
        
        if manual_want is False:
            tags.append("dont_want")
        elif manual_want is True:
            tags.append("manual_want")
        elif derived_want is False:
            tags.append("dont_want")
            
        if rec.get("is_saved"):
            tags.append("saved")
        elif rec.get("is_fetched"):
            tags.append("fetched")
            
        return self.tv.insert("","end", values=vals, tags=tuple(tags))

    def _refresh_alt(self):
        for i, iid in enumerate(self.tv.get_children()):
            cur_tags = self.tv.item(iid,"tags")
            special = [t for t in cur_tags if t in ("fetched","saved","fetching","dont_want","manual_want")]
            if not special:
                self.tv.item(iid, tags=("alt",) if i%2 else ())

    _sort_state = {}
    def _sort(self, col):
        rev = self._sort_state.get(col, False)
        raw_items = [(self.tv.set(k, col), k) for k in self.tv.get_children()]
        
        # Check if column is numeric (Estimated Value, Min Turnover, Exp Yrs, Qty, EMD, etc.)
        is_numeric = False
        if col in ("est_value", "min_turnover", "exp_years", "quantity"):
            is_numeric = True
            
        if is_numeric:
            def clean_num(val):
                cleaned = "".join(c for c in val if c.isdigit() or c in (".", "-"))
                try:
                    return float(cleaned) if cleaned else 0.0
                except ValueError:
                    return 0.0
            raw_items.sort(key=lambda x: clean_num(x[0]), reverse=rev)
        else:
            # Fallback to string collation (case-insensitive)
            raw_items.sort(key=lambda x: x[0].lower(), reverse=rev)
            
        for i, (_, k) in enumerate(raw_items):
            self.tv.move(k, "", i)
            
        self._sort_state[col] = not rev
        
        # Update column headers with sorting indicator arrows
        col_names = {c[0]: c[1] for c in TV_COLS}
        for col_id in list(self.tv.cget("columns")):
            base_name = col_names.get(col_id, col_id)
            if col_id == col:
                indicator = " ▲" if not rev else " ▼"
                self.tv.heading(col_id, text=base_name + indicator)
            else:
                self.tv.heading(col_id, text=base_name)
                
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
        if col_id == "category":
            settings = db.load_settings()
            mappings = settings.get("category_mappings")
            if not mappings:
                try:
                    from config import CATEGORY_MAPPING
                    mappings = [{"name": val, "keywords": kws} for kws, val in CATEGORY_MAPPING]
                except Exception:
                    mappings = []
            category_options = sorted(list(set(m["name"] for m in mappings if m.get("name"))))
            
            e = ttk.Combobox(self.tv, textvariable=var, values=category_options, font=FL)
            # Make it at least 160px wide so category names are readable
            e.place(x=x, y=y, width=max(w, 160), height=h)
            e.focus_set()
            e.select_range(0, "end")
            # Auto-open dropdown so user sees choices immediately
            e.after(50, e.event_generate, "<<ComboboxDropdown>>")
        elif col_id == "filing_status":
            status_options = ["To Be Filed", "Evaluating", "Filed"]
            e = ttk.Combobox(self.tv, textvariable=var, values=status_options, font=FL, state="readonly")
            e.place(x=x, y=y, width=w, height=h)
            e.focus_set()
        else:
            e = tk.Entry(self.tv, textvariable=var, bg=SEL_BG, fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=FL,
                         highlightthickness=0)
            e.place(x=x, y=y, width=w, height=h)
            e.focus_set()
            e.select_range(0, "end")
        self._editing = (iid, col_id, e)
        def commit(ev=None):
            if not self._editing:
                return
            self._editing = None
            # Use the StringVar (textvariable) — most reliable source,
            # especially after <<ComboboxSelected>> fires.
            nv = var.get()
            self.tv.set(iid, col_id, nv)
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                changed_rec = None
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        r[col_id] = nv
                        changed_rec = r
                        if col_id == "category":
                            import parser
                            parser.learn_category_mapping(r.get("items"), nv)
                            parser.assign_tender_status(r)
                            self.tv.set(iid, "filing_status", r["filing_status"])
                        break
                if col_id == "category":
                    self._refresh_table_view()
                # Direct targeted DB update for the changed record
                if changed_rec is not None:
                    db.upsert_tender_field(bid_no, col_id, nv)
                # If category changed, optionally ask LLM for keyword suggestions
                if col_id == "category":
                    try:
                        settings = db.load_settings()
                        if settings.get("llm_use_mapping") and settings.get("llm_provider") and settings.get("llm_provider") != "Disabled":
                            import llm
                            provider = settings.get("llm_provider")
                            api_key = settings.get("llm_api_key", "")
                            base_url = settings.get("llm_base_url", "")
                            model = settings.get("llm_model", "")
                            kws = llm.suggest_category_keywords(changed_rec.get("items") or changed_rec.get("category") or "", provider, api_key, base_url, model)
                            if kws:
                                # show simple review dialog
                                def open_review():
                                    dlg = tk.Toplevel(self)
                                    dlg.transient(self)
                                    dlg.grab_set()
                                    dlg.title("LLM Keyword Suggestions")
                                    dlg.geometry("420x220")
                                    tk.Label(dlg, text=f"LLM suggested keywords for '{nv}':", font=FL).pack(anchor="w", padx=10, pady=(8,4))
                                    vars = {}
                                    box = tk.Frame(dlg)
                                    box.pack(fill="both", expand=True, padx=10)
                                    for k in kws:
                                        v = tk.BooleanVar(value=True)
                                        vars[k]=v
                                        chk = tk.Checkbutton(box, text=k, variable=v, bg=PANEL, fg=TEXT, selectcolor=BG)
                                        chk.pack(anchor="w")

                                    def accept():
                                        selected = [kk for kk, vv in vars.items() if vv.get()]
                                        if selected:
                                            settings2 = db.load_settings()
                                            mappings = settings2.get("category_mappings") or []
                                            ent = None
                                            for m in mappings:
                                                if m.get("name","").lower() == nv.lower():
                                                    ent = m; break
                                            if not ent:
                                                ent = {"name": nv, "keywords": []}
                                                mappings.append(ent)
                                            for s in selected:
                                                if s not in ent["keywords"]:
                                                    ent["keywords"].append(s)
                                            db.save_setting("category_mappings", mappings)
                                        dlg.destroy()

                                    def cancel():
                                        dlg.destroy()

                                    btns = tk.Frame(dlg)
                                    btns.pack(fill="x", pady=8)
                                    tk.Button(btns, text="Accept", command=accept, bg=ACCENT2).pack(side="right", padx=8)
                                    tk.Button(btns, text="Cancel", command=cancel, bg=CARD).pack(side="right")
                                try:
                                    open_review()
                                except Exception:
                                    pass
                    except Exception:
                        pass
            try:
                e.destroy()
            except:
                pass
            db.save_all_tenders(self._records)
            try:
                selected_tab = self.notebook.index(self.notebook.select())
                if selected_tab == 1:
                    self._update_calendar()
                    self._update_details()
                elif selected_tab == 2:
                    self._update_analytics()
            except:
                pass
        def on_focus_out(ev):
            # Delay check slightly so <<ComboboxSelected>> has time to fire and update StringVar
            def check():
                try:
                    if not self._editing:
                        return
                    focus = self.focus_get()
                    # If focus is still within the combobox or its popdown dropdown list, do not close
                    if focus and (str(focus).startswith(str(e)) or "popdown" in str(focus).lower()):
                        return
                    commit()
                except Exception:
                    pass
            e.after(150, check)

        e.bind("<Return>", commit)
        e.bind("<Tab>", commit)
        e.bind("<Escape>", lambda ev: self._cancel_edit())
        if col_id in ("category", "filing_status"):
            e.bind("<<ComboboxSelected>>", commit)
            e.bind("<FocusOut>", on_focus_out)
        else:
            # Plain Entry: commit when focus leaves
            e.bind("<FocusOut>", commit)

    def _cancel_edit(self, event=None):
        if self._editing:
            try:
                self._editing[2].unbind("<FocusOut>")
                self._editing[2].destroy()
            except:
                pass
            self._editing = None

    def _sel_all(self):
        self.tv.selection_set(self.tv.get_children())

    def _del_sel(self):
        sel = self.tv.selection()
        if not sel: return
        
        bids_to_del = []
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                bids_to_del.append(bid_no)
                
        self._records = [r for r in self._records if r.get("bid_no") not in bids_to_del]
        
        self._refresh_table_view()
        self._log("info", f"Deleted {len(sel)} row(s).")
        db.save_all_tenders(self._records)
        try:
            if self.notebook.index(self.notebook.select()) == 1:
                self._update_calendar()
                self._update_details()
        except:
            pass

    def _save_selected(self):
        sel = self.tv.selection()
        if not sel:
            self._log("warn","No rows selected."); return
        folder = self.save_folder.get().strip()
        if not folder:
            self._set_status("Set output folder first.", ERR); return
        os.makedirs(folder, exist_ok=True)
        fy   = financial_year(datetime.now())
        pat  = db.load_settings().get("excel_filename_pattern", "GEM_Tenders_FY_{fy}")
        path = xl_path(folder, fy, pattern=pat)
        ensure_workbook(path)
        
        # Resolve selected records by bid_no
        recs = []
        bids_saved = []
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        recs.append(r)
                        bids_saved.append(bid_no)
                        break
        try:
            snos = xl_append(path, recs)
            msg = f"Saved {len(snos)} row(s) → {os.path.basename(path)}  (S.No {snos[0]}–{snos[-1]})"
            self._log("ok", msg); self._set_status(msg, SUCCESS); self._fy_tick()
            
            # Tag the rows in Treeview
            for iid in sel: 
                self.tv.item(iid, tags=("saved",))
                
            # Update records structure
            for r in self._records:
                if r.get("bid_no") in bids_saved:
                    r["is_saved"] = True
                    
            db.save_all_tenders(self._records)
        except Exception as ex:
            self._log("err", f"Save error: {ex}")
            messagebox.showerror("Save Error", str(ex))

    def _on_tab_changed(self, event):
        try:
            selected_tab = self.notebook.index(self.notebook.select())
            if selected_tab == 1:
                self._update_calendar()
                self._update_details()
            elif selected_tab == 2:
                self._update_analytics()
        except Exception as e:
            self._log("err", f"Tab changed error: {e}")

    def _get_tender_status(self, rec, inc_kws, exc_kws):
        is_want = rec.get("is_want")
        if is_want is not None:
            return is_want
            
        search_fields = [
            rec.get("items", ""),
            rec.get("category", ""),
            rec.get("ministry", ""),
            rec.get("dept", ""),
            rec.get("organisation", ""),
            rec.get("location", ""),
            rec.get("bid_no", "")
        ]
        combined_text = " ".join(search_fields).lower()
        
        def check_single_rule(rule):
            rule_clean = rule.strip()
            if not rule_clean:
                return False
            
            # Regex Rule Support
            if rule_clean.lower().startswith("rx:"):
                pattern = rule_clean[3:].strip()
                try:
                    import re
                    return bool(re.search(pattern, combined_text, re.I))
                except Exception:
                    return False
                    
            # Boolean Expression Support
            if " and " in rule_clean.lower() or " or " in rule_clean.lower() or "not " in rule_clean.lower() or "(" in rule_clean or ")" in rule_clean:
                return eval_expr(rule_clean.lower())
                
            # Smart keyword boundary matching for short words
            if rule_clean.isalnum() and len(rule_clean) <= 3:
                import re
                pattern = r"\b" + re.escape(rule_clean.lower()) + r"\b"
                return bool(re.search(pattern, combined_text, re.I))
                
            # Standard Plain Substring Matching
            return rule_clean.lower() in combined_text

        def eval_expr(expr):
            import re
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

        # Check firms if configured
        settings = db.load_settings()
        firms = settings.get("firms", [])
        if firms:
            matched_firms = []
            for firm in firms:
                # 1. Exclude keywords
                exc_raw = firm.get("exclude_keywords", "")
                exc_list = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
                is_excluded = False
                for kw in exc_list:
                    if check_single_rule(kw):
                        is_excluded = True
                        break
                if is_excluded:
                    continue
                    
                # 2. Categories (Include Keywords)
                cat_raw = firm.get("categories", "")
                cat_list = [k.strip().lower() for k in cat_raw.split(",") if k.strip()]
                cat_match = False
                if cat_list:
                    for kw in cat_list:
                        if check_single_rule(kw):
                            cat_match = True
                            break
                else:
                    cat_match = True  # If empty, treat as matching
                    
                if not cat_match:
                    continue
                    
                # 3. Locations
                loc_raw = firm.get("locations", "")
                loc_list = [k.strip().lower() for k in loc_raw.split(",") if k.strip()]
                loc_match = False
                if loc_list:
                    for kw in loc_list:
                        if check_single_rule(kw):
                            loc_match = True
                            break
                else:
                    loc_match = True  # If empty, treat as matching
                    
                if not loc_match:
                    continue
                    
                matched_firms.append(firm.get("name", "Unnamed Firm"))
                
            if matched_firms:
                rec["matched_firm"] = ", ".join(matched_firms)
                return True
            else:
                rec["matched_firm"] = ""
                return False

        # Fallback to global include/exclude rules if no firms are configured
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

    def _is_bid_in_dont_wants(self, bid_no_or_id):
        if not bid_no_or_id:
            return False
        target = bid_no_or_id.strip().lower()
        
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]

        for r in self._records:
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
                is_want = self._get_tender_status(r, inc_kws, exc_kws)
                if not is_want:
                    return r
        return None

    def _refresh_table_view(self):
        import threading
        if threading.current_thread() is not threading.main_thread():
            self.after(0, self._refresh_table_view)
            return

        if not hasattr(self, "tv") or self.tv is None:
            return
        for child in self.tv.get_children():
            self.tv.delete(child)
            
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
        is_semantic = False
        if "semantic_search_var" in self.__dict__:
            try:
                is_semantic = self.semantic_search_var.get() and search_text
            except Exception:
                pass
        semantic_ranks = {}
        if is_semantic:
            # Run semantic search in FAISS
            results = semantic_search(search_text, limit=100)
            semantic_ranks = {bid_no: idx for idx, (bid_no, _) in enumerate(results)}

        # Sort/Filter records list for iteration
        records_to_render = self._records
        if is_semantic:
            # Filter to only those matched by semantic search, and sort by relevance rank
            matched_recs = [r for r in self._records if r.get("bid_no") in semantic_ranks]
            matched_recs.sort(key=lambda r: semantic_ranks[r["bid_no"]])
            records_to_render = matched_recs
        
        visible_count = 0
        for rec in records_to_render:
            is_want = self._get_tender_status(rec, inc_kws, exc_kws)
            rec["is_want_derived"] = is_want
            
            if view_filter == "Wants (Matches)" and not is_want:
                continue
            if view_filter == "Don't Wants (Filtered)" and is_want:
                continue

            # Apply Status View filter
            if "status_view_var" in self.__dict__:
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
                    
            self._tv_insert(rec)
            visible_count += 1
            
        self._refresh_alt()
        self.count_lbl.configure(text=f"{visible_count} visible / {len(self._records)} total")

    def _show_context_menu(self, event):
        region = self.tv.identify_region(event.x, event.y)
        if region == "heading":
            column_id = self.tv.identify_column(event.x)
            try:
                col_index = int(column_id[1:]) - 1
                display_cols = list(self.tv.cget("displaycolumns"))
                if display_cols == ["#all"] or not display_cols:
                    settings = db.load_settings()
                    visible = settings.get("visible_columns")
                    if not visible or not isinstance(visible, list):
                        display_cols = [c[0] for c in TV_COLS]
                    else:
                        display_cols = visible
                
                if 0 <= col_index < len(display_cols):
                    target_col = display_cols[col_index]
                    
                    # Create header context menu
                    hdr_menu = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=ACCENT, activeforeground=TEXT)
                    
                    # Move Left
                    if col_index > 0:
                        def move_left():
                            cols = list(display_cols)
                            cols[col_index], cols[col_index - 1] = cols[col_index - 1], cols[col_index]
                            db.save_setting("visible_columns", cols)
                            self._apply_column_visibility()
                        hdr_menu.add_command(label="◀ Move Left", command=move_left)
                    else:
                        hdr_menu.add_command(label="◀ Move Left", state="disabled")
                        
                    # Move Right
                    if col_index < len(display_cols) - 1:
                        def move_right():
                            cols = list(display_cols)
                            cols[col_index], cols[col_index + 1] = cols[col_index + 1], cols[col_index]
                            db.save_setting("visible_columns", cols)
                            self._apply_column_visibility()
                        hdr_menu.add_command(label="▶ Move Right", command=move_right)
                    else:
                        hdr_menu.add_command(label="▶ Move Right", state="disabled")
                        
                    hdr_menu.add_separator()
                    
                    # Hide Column
                    def hide_col():
                        cols = list(display_cols)
                        cols.remove(target_col)
                        if not cols:
                            cols = ["bid_no"]
                        db.save_setting("visible_columns", cols)
                        self._apply_column_visibility()
                    hdr_menu.add_command(label="👁 Hide Column", command=hide_col)
                    
                    # Manage Columns
                    hdr_menu.add_command(label="⚙ Manage Columns...", command=self._show_column_selector)
                    
                    hdr_menu.post(event.x_root, event.y_root)
                    return
            except Exception as e:
                self._log("err", f"Header menu error: {e}")

        iid = self.tv.identify_row(event.y)
        if iid:
            if iid not in self.tv.selection():
                self.tv.selection_set(iid)
                
            # Dynamically set PDF options state
            bid_no = self.tv.set(iid, "bid_no")
            rec = None
            for r in self._records:
                if r.get("bid_no") == bid_no:
                    rec = r
                    break
            
            pdf_path = rec.get("pdf_path", "") if rec else ""
            if pdf_path:
                self.ctx_menu.entryconfigure("Open Associated PDF", state="normal")
                self.ctx_menu.entryconfigure("Unlink PDF File", state="normal")
            else:
                self.ctx_menu.entryconfigure("Open Associated PDF", state="disabled")
                self.ctx_menu.entryconfigure("Unlink PDF File", state="disabled")
                
            self.ctx_menu.post(event.x_root, event.y_root)

    def _mark_selected_want(self):
        sel = self.tv.selection()
        if not sel: return
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        r["is_want"] = True
                        break
        db.save_all_tenders(self._records)
        self._refresh_table_view()
        self._log("ok", f"Marked {len(sel)} tender(s) as Want.")

    def _mark_selected_dont_want(self):
        sel = self.tv.selection()
        if not sel: return
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        r["is_want"] = False
                        break
        db.save_all_tenders(self._records)
        self._refresh_table_view()
        self._log("ok", f"Marked {len(sel)} tender(s) as Don't Want.")

    def _reset_selected_tag(self):
        sel = self.tv.selection()
        if not sel: return
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        r.pop("is_want", None)
                        break
        db.save_all_tenders(self._records)
        self._refresh_table_view()
        self._log("info", f"Reset manual tag for {len(sel)} tender(s).")

    def _set_selected_filing_status(self, status):
        sel = self.tv.selection()
        if not sel:
            return
        updated_count = 0
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        r["filing_status"] = status
                        updated_count += 1
                        break
                # Update UI Treeview row
                self.tv.set(iid, "filing_status", status)
                # Update Database
                db.upsert_tender_field(bid_no, "filing_status", status)
                
        if updated_count > 0:
            self._log("ok", f"Set filing status to '{status}' for {updated_count} tender(s).")
            self._refresh_table_view()
            # Cascade view refreshes if active
            try:
                selected_tab = self.notebook.index(self.notebook.select())
                if selected_tab == 1:
                    self._update_calendar()
                    self._update_details()
                elif selected_tab == 2:
                    self._update_analytics()
            except Exception:
                pass

    def _copy_table_output(self):
        headers = [c[1] for c in TV_COLS]
        lines = ["\t".join(headers)]
        
        selected = self.tv.selection()
        rows_to_copy = selected if selected else self.tv.get_children()
        
        if not rows_to_copy:
            self._log("warn", "No data to copy.")
            return
            
        for iid in rows_to_copy:
            vals = [str(self.tv.set(iid, c[0])) for c in TV_COLS]
            lines.append("\t".join(vals))
            
        text_to_copy = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text_to_copy)
        self.update()
        
        count = len(rows_to_copy)
        scope = "selected" if selected else "all visible"
        self._log("ok", f"Copied {count} {scope} row(s) to clipboard.")

    def _on_date_combo_changed(self):
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
                    self._refresh_table_view()
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
            self._refresh_table_view()

    def _clear_detail_panel(self):
        self.detail_txt.configure(state="normal")
        self.detail_txt.delete("1.0", "end")
        self.detail_txt.insert("end", "\n\nSelect a tender from the table to view its full details here.", "value")
        self.detail_txt.configure(state="disabled")
        
        if hasattr(self, "pdf_lbl"):
            self.pdf_lbl.configure(text="PDF: Not Linked", fg=TEXTSUB)
            self.btn_open_pdf.configure(state="disabled")
            self.btn_unlink_pdf.configure(state="disabled")

    def _on_treeview_select(self, event):
        sel = self.tv.selection()
        if not sel:
            self._clear_detail_panel()
            return
            
        # Get selected record
        bid_no = self.tv.set(sel[0], "bid_no")
        rec = None
        for r in self._records:
            if r.get("bid_no") == bid_no:
                rec = r
                break
        if not rec:
            self._clear_detail_panel()
            return
            
        # Update PDF frame widgets
        pdf_path = rec.get("pdf_path", "")
        if pdf_path:
            import os
            filename = os.path.basename(pdf_path)
            if len(filename) > 25:
                filename = filename[:22] + "..."
            self.pdf_lbl.configure(text=f"PDF: {filename}", fg=SUCCESS)
            self.btn_open_pdf.configure(state="normal")
            self.btn_unlink_pdf.configure(state="normal")
        else:
            self.pdf_lbl.configure(text="PDF: Not Linked", fg=TEXTSUB)
            self.btn_open_pdf.configure(state="disabled")
            self.btn_unlink_pdf.configure(state="disabled")

        self.detail_txt.configure(state="normal")
        self.detail_txt.delete("1.0", "end")
        
        # Display fields in group categories
        categories = {
            "Basic Info": ["bid_no", "bid_url", "category", "items", "quantity", "location"],
            "Department Info": ["ministry", "dept", "organisation", "office"],
            "Dates & Schedule": ["start_date", "end_date", "bid_opening"],
            "Financial Details": ["est_value", "emd", "epbg", "min_turnover"],
            "Qualifications": ["exp_years", "contract_dur", "mii", "mse_pref", "mse_relax", "startup_relax"],
            "Status & Metadata": ["filing_status", "tags", "remarks", "pdf_path"]
        }
        
        # Mapping DB field keys to human readable labels
        labels = {
            "bid_no": "Bid Number", "bid_url": "Bid URL", "category": "Category", "items": "Items", 
            "quantity": "Quantity", "location": "Location/Consignee", "ministry": "Ministry", 
            "dept": "Department", "organisation": "Organisation", "office": "Office", 
            "start_date": "Start Date", "end_date": "End Date", "bid_opening": "Bid Opening Date", 
            "est_value": "Estimated Value", "emd": "EMD Required", "epbg": "ePBG Required", 
            "min_turnover": "Min Turnover", "exp_years": "Exp Years Required", "contract_dur": "Contract Duration", 
            "mii": "MII Compliant", "mse_pref": "MSE Pref", "mse_relax": "MSE Relaxation", 
            "startup_relax": "Startup Relaxation", "filing_status": "Filing Status", "tags": "Tags", 
            "remarks": "Remarks", "pdf_path": "Associated PDF"
        }
        
        first = True
        for cat_name, fields in categories.items():
            if not first:
                self.detail_txt.insert("end", "\n\n")
            first = False
            
            # Print Category Header
            self.detail_txt.insert("end", f"■ {cat_name}\n", "header")
            self.detail_txt.insert("end", "─" * 32 + "\n", "label")
            
            for field in fields:
                val = rec.get(field, "")
                if field == "tags":
                    if isinstance(val, list):
                        val = ", ".join(val)
                    elif not val:
                        val = "None"
                elif isinstance(val, bool):
                    val = "Yes" if val else "No"
                else:
                    val = str(val).strip()
                    
                if not val:
                    val = "N/A"
                    
                lbl = labels.get(field, field.capitalize())
                self.detail_txt.insert("end", f"{lbl}: ", "label")
                self.detail_txt.insert("end", f"{val}\n", "value")
                
        # Highlight match words (include / exclude keywords)
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        
        inc_kws = [k.strip() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip() for k in exc_raw.split(",") if k.strip()]
        
        # Apply include tags (case-insensitive)
        for kw in inc_kws:
            start = "1.0"
            while True:
                pos = self.detail_txt.search(kw, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos} + {len(kw)}c"
                self.detail_txt.tag_add("match_inc", pos, end)
                start = end
                
        # Apply exclude tags (case-insensitive)
        for kw in exc_kws:
            start = "1.0"
            while True:
                pos = self.detail_txt.search(kw, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos} + {len(kw)}c"
                self.detail_txt.tag_add("match_exc", pos, end)
                start = end
                
        # Highlight firm-specific words
        firms = settings.get("firms", [])
        for firm in firms:
            # 1. Categories
            for kw in [k.strip() for k in firm.get("categories", "").split(",") if k.strip()]:
                start = "1.0"
                while True:
                    pos = self.detail_txt.search(kw, start, stopindex="end", nocase=True)
                    if not pos:
                        break
                    end = f"{pos} + {len(kw)}c"
                    self.detail_txt.tag_add("match_firm_inc", pos, end)
                    start = end
            # 2. Locations
            for kw in [k.strip() for k in firm.get("locations", "").split(",") if k.strip()]:
                start = "1.0"
                while True:
                    pos = self.detail_txt.search(kw, start, stopindex="end", nocase=True)
                    if not pos:
                        break
                    end = f"{pos} + {len(kw)}c"
                    self.detail_txt.tag_add("match_firm_loc", pos, end)
                    start = end
            # 3. Excludes
            for kw in [k.strip() for k in firm.get("exclude_keywords", "").split(",") if k.strip()]:
                start = "1.0"
                while True:
                    pos = self.detail_txt.search(kw, start, stopindex="end", nocase=True)
                    if not pos:
                        break
                    end = f"{pos} + {len(kw)}c"
                    self.detail_txt.tag_add("match_firm_exc", pos, end)
                    start = end
                
        # Highlight active search query
        search_query = self.search_var.get().strip()
        if search_query:
            start = "1.0"
            while True:
                pos = self.detail_txt.search(search_query, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos} + {len(search_query)}c"
                self.detail_txt.tag_add("match_search", pos, end)
                start = end
                
        self.detail_txt.configure(state="disabled")

    def _bind_shortcuts(self):
        self.bind("<Control-f>", lambda e: self._shortcut_focus_search())
        self.bind("<Control-s>", lambda e: self._shortcut_focus_search())
        self.bind("<Control-v>", lambda e: self._shortcut_clipboard_parse())
        self.bind("<Control-r>", lambda e: self._reload())
        self.bind("<Control-Alt-s>", lambda e: self._show_settings())
        self.bind("<Delete>", lambda e: self._shortcut_delete_selected())
        self.bind("<Escape>", lambda e: self._cancel_edit())

    def _shortcut_focus_search(self):
        try:
            self.notebook.select(0)
            self.search_ent.focus_set()
            self.search_ent.selection_range(0, "end")
        except Exception:
            pass
        return "break"

    def _shortcut_clipboard_parse(self):
        # If focus is on any text input widget, let the native paste work
        focused = self.focus_get()
        if isinstance(focused, (tk.Text, tk.Entry)):
            return
        try:
            clipboard = self.clipboard_get()
            if clipboard:
                self.notebook.select(2)
                self.paste_txt.delete("1.0", "end")
                self.paste_txt.insert("1.0", clipboard)
                self._do_parse()
        except Exception:
            pass
        return "break"

    def _shortcut_delete_selected(self):
        try:
            if self.notebook.index(self.notebook.select()) == 0:
                self._del_sel()
        except Exception:
            pass
        return "break"

    def _show_datepicker(self, button, var):
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        DatePickerPopup(self, var, x, y)

    def _link_associated_pdf(self):
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
        for r in self._records:
            if r.get("bid_no") == bid_no:
                r["pdf_path"] = file_path
                updated = True
                break
                
        if updated:
            import db
            db.upsert_tender_field(bid_no, "pdf_path", file_path)
            self._log("ok", f"Linked PDF to {bid_no}: {os.path.basename(file_path)}")
            self._on_treeview_select(None)

    def _unlink_associated_pdf(self):
        sel = self.tv.selection()
        if not sel:
            return
        bid_no = self.tv.set(sel[0], "bid_no")
        if not bid_no:
            return
            
        updated = False
        for r in self._records:
            if r.get("bid_no") == bid_no:
                r["pdf_path"] = ""
                updated = True
                break
                
        if updated:
            import db
            db.upsert_tender_field(bid_no, "pdf_path", "")
            self._log("info", f"Unlinked PDF for {bid_no}")
            self._on_treeview_select(None)

    def _open_associated_pdf(self):
        sel = self.tv.selection()
        if not sel:
            return
        bid_no = self.tv.set(sel[0], "bid_no")
        if not bid_no:
            return
            
        rec = None
        for r in self._records:
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
            self._log("ok", f"Opened PDF for {bid_no}")
        except Exception as e:
            try:
                webbrowser.open(f"file:///{os.path.abspath(pdf_path)}")
                self._log("ok", f"Opened PDF for {bid_no} in browser")
            except Exception as ex:
                self._log("err", f"Failed to open PDF: {e}")
                messagebox.showerror("Open Error", f"Could not open PDF file:\n{e}")

    def _apply_column_visibility(self):
        settings = db.load_settings()
        visible = settings.get("visible_columns")
        if not visible or not isinstance(visible, list):
            visible = [c[0] for c in TV_COLS]
        
        valid_cols = [c[0] for c in TV_COLS]
        visible = [col for col in visible if col in valid_cols]
        if not visible:
            visible = valid_cols
            
        self.tv.configure(displaycolumns=visible)

    def _show_column_selector(self):
        win = tk.Toplevel(self)
        win.title("Select Columns")
        win.geometry("400x520")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.transient(self)
        win.grab_set()
        
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 520) // 2
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
        
        # Load visible columns and custom order from settings
        settings = db.load_settings()
        visible = settings.get("visible_columns")
        if not visible or not isinstance(visible, list):
            visible = [c[0] for c in TV_COLS]
            
        # Compile list of all column objects in their current order
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
            self._apply_column_visibility()
            win.destroy()
            
        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(fill="x", pady=15)
        
        self._btn(btn_frame, "  Apply  ", save_columns, bg=ACCENT2).pack(side="left", padx=(40, 10), expand=True, fill="x")
        self._btn(btn_frame, "  Cancel  ", win.destroy, bg=CARD).pack(side="right", padx=(10, 40), expand=True, fill="x")
