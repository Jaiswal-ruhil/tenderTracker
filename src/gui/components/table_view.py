import tkinter as tk
from tkinter import ttk, messagebox
import re
from datetime import datetime, date

# Local imports
from config import (
    BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN, SEL_BG,
    FL, TV_COLS, TV_IDS, URGENT_BG, WARN_BG, CLOSED_FG
)
import db

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
        self.tip_window = None
        self.after_id   = None
        self.last_cell  = None  # (iid, col_id)

        self.tv.bind("<Motion>", self._on_motion, add="+")
        self.tv.bind("<Leave>", self._hide, add="+")
        self.tv.bind("<Button-1>", self._hide, add="+")

    def _on_motion(self, event):
        # Identify row and column
        iid = self.tv.identify_row(event.y)
        col = self.tv.identify_column(event.x)
        
        if not iid or not col:
            self._hide_tip()
            self.last_cell = None
            return

        # Convert col string like "#3" to 0-based column index
        try:
            col_idx = int(col[1:]) - 1
            if col_idx < 0 or col_idx >= len(self.tv_ids):
                raise ValueError
            col_id = self.tv_ids[col_idx]
        except ValueError:
            self._hide_tip()
            self.last_cell = None
            return

        current_cell = (iid, col_id)
        if current_cell != self.last_cell:
            self._hide_tip()
            self.last_cell = current_cell
            
            # Fetch cell value
            val = str(self.tv.set(iid, col_id)).strip()
            if len(val) >= self.MIN_CHARS:
                # Schedule tooltip popup
                x_root = event.x_root + 15
                y_root = event.y_root + 15
                self.after_id = self.tv.after(
                    self.DELAY_MS,
                    lambda: self._show(val, col_id, x_root, y_root)
                )

    def _show(self, text, col_id, x, y):
        self._hide_tip()
        
        # Word wrapping helper
        import textwrap
        lines = []
        for line in text.split("\n"):
            lines.extend(textwrap.wrap(line, width=self.WRAP_CHARS, break_long_words=False))
            
        if len(lines) > self.MAX_LINES:
            lines = lines[:self.MAX_LINES]
            lines.append("... [truncated]")
            
        wrapped_text = "\n".join(lines)
        
        # Create tooltip window
        self.tip_window = tw = tk.Toplevel(self.tv)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        
        # Visual style
        lbl = tk.Label(
            tw, text=wrapped_text, justify="left",
            bg="#1C2128", fg="#C9D1D9",
            relief="solid", borderwidth=1,
            highlightthickness=0,
            font=("Segoe UI", 9),
            padx=10, pady=8
        )
        lbl.pack(ipadx=1, ipady=1)

    def _hide_tip(self):
        if self.after_id:
            self.tv.after_cancel(self.after_id)
            self.after_id = None
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

    def _hide(self, event=None):
        self._hide_tip()
        self.last_cell = None


class TendersTableView(tk.Frame):
    def __init__(self, parent, app, table_tab):
        super().__init__(parent, bg=BG)
        self.app = app
        self.table_tab = table_tab
        self._editing = None
        self._sort_state = {}

        cols = [c[0] for c in TV_COLS]
        self.tv = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        for cid, lbl, w in TV_COLS:
            self.tv.heading(cid, text=lbl, command=lambda c=cid: self.sort(c))
            # Keep columns readable when users resize headers; long tender
            # fields remain available through the horizontal scrollbar.
            self.tv.column(cid, width=w, minwidth=max(80, int(w * 0.65)), stretch=False)

        vsb = ttk.Scrollbar(self, orient="vertical",   command=self.tv.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tv.xview)
        self.tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tv.bind("<Double-1>", self.on_dbl)
        self.tv.bind("<Button-1>", self.cancel_edit)
        self.tv.bind("<<TreeviewSelect>>", self.table_tab.on_treeview_select)

        # Alternating row background configure
        self.tv.tag_configure("alt",         background="#1C2128")
        self.tv.tag_configure("fetched",     background="#1A2E1A", foreground=SUCCESS)
        self.tv.tag_configure("saved",       background="#1A3A2A", foreground=SUCCESS)
        self.tv.tag_configure("fetching",    background="#2A2A1A", foreground=WARN)
        self.tv.tag_configure("dont_want",   foreground="#5D6570")
        self.tv.tag_configure("manual_want", background="#1A3324")
        
        # Deadline urgency tags
        self.tv.tag_configure("urgent",  background=URGENT_BG, foreground="#FF8A8A")
        self.tv.tag_configure("warn_dl", background=WARN_BG,   foreground="#FFD080")
        self.tv.tag_configure("closed",  foreground=CLOSED_FG)

        self._cell_tooltip = CellTooltip(self.tv, TV_IDS)
        self._treeview_hover = TreeviewHover(self.tv)

    @staticmethod
    def _compute_closing_in(end_date_str):
        """Return a human-readable countdown string and urgency level."""
        if not end_date_str:
            return "", None
        try:
            # Parse common formats: dd-mm-yyyy, dd/mm/yyyy, yyyy-mm-dd
            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y %I:%M %p",
                        "%d-%m-%Y %H:%M"):
                try:
                    dt = datetime.strptime(str(end_date_str).strip()[:16], fmt[:len(fmt)])
                    break
                except ValueError:
                    continue
            else:
                return "", None
            now = datetime.now()
            delta = dt - now
            total_secs = delta.total_seconds()
            if total_secs < 0:
                return "Closed", "closed"
            hours = total_secs / 3600
            if hours <= 24:
                h = int(hours)
                m = int((total_secs % 3600) / 60)
                return f"{h}h {m}m", "urgent"
            elif hours <= 72:
                days = int(total_secs // 86400)
                hrs  = int((total_secs % 86400) // 3600)
                return f"{days}d {hrs}h", "warn_dl"
            else:
                days = int(total_secs // 86400)
                return f"{days}d", None
        except Exception:
            return "", None

    def tv_insert(self, rec):
        raw_vals = []
        for c in TV_IDS:
            if c == "closing_in":
                ci, _ = self._compute_closing_in(rec.get("end_date", ""))
                raw_vals.append(ci)
            else:
                val = rec.get(c, "")
                if c == "tags" and isinstance(val, list):
                    val = ", ".join(val)
                raw_vals.append(val)
        vals = tuple(raw_vals)
        tags = []

        # Urgency deadline tag (only for Want tenders)
        manual_want = rec.get("is_want")
        derived_want = rec.get("is_want_derived", True)
        is_want_row = (manual_want is True) or (manual_want is None and derived_want is not False)

        _, urgency = self._compute_closing_in(rec.get("end_date", ""))
        if urgency == "closed":
            tags.append("closed")
        elif is_want_row and urgency:
            tags.append(urgency)

        # Wants / Don't Wants tags
        if manual_want is False:
            tags = ["dont_want"]          # override urgency for dont-wants
        elif manual_want is True:
            tags.append("manual_want")
        elif derived_want is False:
            tags = ["dont_want"]

        if rec.get("is_saved"):
            tags.append("saved")
        elif rec.get("is_fetched"):
            tags.append("fetched")

        return self.tv.insert("", "end", values=vals, tags=tuple(tags))

    def refresh_alt(self):
        for i, iid in enumerate(self.tv.get_children()):
            cur_tags = self.tv.item(iid, "tags")
            special = [t for t in cur_tags if t in ("fetched", "saved", "fetching", "dont_want", "manual_want")]
            if not special:
                self.tv.item(iid, tags=("alt",) if i % 2 else ())

    def sort(self, col):
        rev = self._sort_state.get(col, False)
        raw_items = [(self.tv.set(k, col), k) for k in self.tv.get_children()]
        
        is_numeric = col in ("est_value", "min_turnover", "exp_years", "quantity")
            
        if is_numeric:
            def clean_num(val):
                cleaned = "".join(c for c in val if c.isdigit() or c in (".", "-"))
                try:
                    return float(cleaned) if cleaned else 0.0
                except ValueError:
                    return 0.0
            raw_items.sort(key=lambda x: clean_num(x[0]), reverse=rev)
        else:
            raw_items.sort(key=lambda x: x[0].lower(), reverse=rev)
            
        for i, (_, k) in enumerate(raw_items):
            self.tv.move(k, "", i)
            
        self._sort_state[col] = not rev
        
        col_names = {c[0]: c[1] for c in TV_COLS}
        for col_id in list(self.tv.cget("columns")):
            base_name = col_names.get(col_id, col_id)
            if col_id == col:
                indicator = " ▲" if not rev else " ▼"
                self.tv.heading(col_id, text=base_name + indicator)
            else:
                self.tv.heading(col_id, text=base_name)
                
        self.refresh_alt()

    def on_dbl(self, event):
        region = self.tv.identify_region(event.x, event.y)
        if region != "cell": return
        col = self.tv.identify_column(event.x)
        iid = self.tv.identify_row(event.y)
        if not iid: return
        col_idx = int(col[1:]) - 1
        if col_idx >= len(TV_IDS): return
        col_id = TV_IDS[col_idx]
        bbox = self.tv.bbox(iid, col)
        if not bbox: return
        x, y, w, h = bbox
        var = tk.StringVar(value=self.tv.set(iid, col_id))
        
        if col_id == "category":
            settings = db.load_settings()
            mappings = settings.get("category_mappings") or []
            category_options = sorted(list(set(m["name"] for m in mappings if m.get("name"))))
            
            e = ttk.Combobox(self.tv, textvariable=var, values=category_options, font=FL)
            e.place(x=x, y=y, width=max(w, 160), height=h)
            e.focus_set()
            e.select_range(0, "end")
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
            
        self.app._editing = (iid, col_id, e)
        self._editing = (iid, col_id, e)
        
        def commit(ev=None):
            if not self._editing:
                return
            self._editing = None
            self.app._editing = None
            nv = var.get()
            self.tv.set(iid, col_id, nv)
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                changed_rec = None
                for r in self.app._records:
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
                    self.table_tab.refresh_table_view()
                if changed_rec is not None:
                    db.upsert_tender_field(bid_no, col_id, nv)
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
                                def open_review():
                                    dlg = tk.Toplevel(self)
                                    dlg.transient(self.app)
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
                                    self.app._btn(btns, "Accept", accept, bg=ACCENT2).pack(side="right", padx=8)
                                    self.app._btn(btns, "Cancel", cancel, bg=CARD).pack(side="right")
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
            db.save_all_tenders(self.app._records)
            try:
                selected_tab = self.app.notebook.index(self.app.notebook.select())
                if selected_tab == self.app.notebook.index(self.app.tab_calendar):
                    self.app._update_calendar()
                    self.app._update_details()
                elif selected_tab == self.app.notebook.index(self.app.tab_analytics):
                    self.app._update_analytics()
            except:
                pass

        def on_focus_out(ev):
            def check():
                try:
                    if not self._editing:
                        return
                    focus = self.app.focus_get()
                    if focus and (str(focus).startswith(str(e)) or "popdown" in str(focus).lower()):
                        return
                    commit()
                except Exception:
                    pass
            e.after(150, check)

        e.bind("<Return>", commit)
        e.bind("<Tab>", commit)
        e.bind("<Escape>", lambda ev: self.cancel_edit())
        if col_id in ("category", "filing_status"):
            e.bind("<<ComboboxSelected>>", commit)
            e.bind("<FocusOut>", on_focus_out)
        else:
            e.bind("<FocusOut>", commit)

    def cancel_edit(self, event=None):
        if self._editing:
            try:
                self._editing[2].unbind("<FocusOut>")
                self._editing[2].destroy()
            except:
                pass
            self._editing = None
            self.app._editing = None
