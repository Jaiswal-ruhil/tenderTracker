import tkinter as tk
from tkinter import ttk
import webbrowser
import db

from config import BG, PANEL, CARD, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR


class KanbanTabMixin:
    def _build_kanban_tab(self):
        self.tab_kanban = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.tab_kanban, text="  Board View  ")

        # container for columns
        cols_fr = tk.Frame(self.tab_kanban, bg=BG)
        cols_fr.pack(fill="both", expand=True, padx=6, pady=6)

        self.kanban_cols = {}
        col_names = ["Evaluating", "To Be Filed", "Filed", "Urgent (Due)"]
        for idx, name in enumerate(col_names):
            fr = tk.Frame(cols_fr, bg=PANEL, padx=8, pady=8, highlightthickness=1, highlightbackground="#30363D")
            fr.grid(row=0, column=idx, sticky="nsew", padx=6, pady=4)
            cols_fr.columnconfigure(idx, weight=1)

            hdr = tk.Label(fr, text=name, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=TEXT)
            hdr.pack(fill="x")

            canvas = tk.Canvas(fr, bg=PANEL, highlightthickness=0)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar = ttk.Scrollbar(fr, orient="vertical", command=canvas.yview)
            scrollbar.pack(side="right", fill="y")
            canvas.configure(yscrollcommand=scrollbar.set)

            inner = tk.Frame(canvas, bg=PANEL)
            canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")

            def _on_cfg(e, c=canvas):
                c.configure(scrollregion=c.bbox("all"))

            inner.bind("<Configure>", _on_cfg)

            self.kanban_cols[name] = inner

        # quick refresh button row
        btns = tk.Frame(self.tab_kanban, bg=BG)
        btns.pack(fill="x")
        self._btn(btns, "Refresh Board", self._update_kanban, bg=ACCENT2).pack(side="left", padx=6, pady=6)

    def _is_urgent(self, rec):
        # consider end_date within 7 days as urgent
        try:
            ed = self._parse_date_str(rec.get("end_date"))
            if not ed:
                return False
            from datetime import date, timedelta
            return ed <= date.today() + timedelta(days=7)
        except Exception:
            return False

    def _update_kanban(self):
        # clear columns
        for col in self.kanban_cols.values():
            for c in col.winfo_children():
                c.destroy()

        # populate
        for r in self._records:
            status = (r.get("filing_status") or "").strip()
            card_col = "To Be Filed"
            if status.lower() == "evaluating":
                card_col = "Evaluating"
            elif status.lower() == "filed":
                card_col = "Filed"

            if self._is_urgent(r):
                card_col = "Urgent (Due)"

            parent = self.kanban_cols.get(card_col) or list(self.kanban_cols.values())[0]

            card = tk.Frame(parent, bg=CARD, padx=8, pady=6, highlightthickness=1, highlightbackground="#30363D")
            card.pack(fill="x", pady=6, padx=4)

            # Enable simple drag-and-drop
            def on_press(e, widget=card):
                widget._drag_start_x = e.x
                widget._drag_start_y = e.y
                widget.lift()

            def on_motion(e, widget=card):
                try:
                    widget.place(in_=self.tab_kanban, x=widget.winfo_x() + e.x - widget._drag_start_x, y=widget.winfo_y() + e.y - widget._drag_start_y)
                except Exception:
                    pass

            def on_release(e, widget=card):
                # Find column under pointer and reparent
                try:
                    x_root = widget.winfo_rootx() + e.x
                    y_root = widget.winfo_rooty() + e.y
                    target = self.tab_kanban.winfo_containing(x_root, y_root)
                    # climb until we find a kanban column inner frame
                    while target and getattr(target, 'master', None):
                        if target in self.kanban_cols.values() or getattr(target, 'tk', None) is None:
                            break
                        target = target.master
                    # If found a valid column, move the card
                    for name, col in self.kanban_cols.items():
                        if target == col or (hasattr(target, 'master') and target.master == col):
                            widget.place_forget()
                            widget.master = col
                            widget.pack(in_=col, fill="x", pady=6, padx=4)
                            # update record filing_status
                            bid_lbl = None
                            for ch in widget.winfo_children():
                                if isinstance(ch, tk.Label) and ch.cget("font") and "bold" in str(ch.cget("font")):
                                    bid_lbl = ch.cget("text")
                                    break
                            if bid_lbl:
                                for rec in self._records:
                                    if rec.get("bid_no") == bid_lbl:
                                        if name == "Evaluating":
                                            rec["filing_status"] = "Evaluating"
                                        elif name == "To Be Filed":
                                            rec["filing_status"] = "To Be Filed"
                                        elif name == "Filed":
                                            rec["filing_status"] = "Filed"
                                        elif name == "Urgent (Due)":
                                            rec["filing_status"] = "To Be Filed"
                                        try:
                                            import db
                                            db.save_all_tenders(self._records)
                                        except Exception:
                                            pass
                            break
                except Exception:
                    pass

            card.bind("<Button-1>", on_press)
            card.bind("<B1-Motion>", on_motion)
            card.bind("<ButtonRelease-1>", on_release)

            tk.Label(card, text=r.get("bid_no",""), font=("Segoe UI",9,"bold"), bg=CARD, fg=TEXT).pack(anchor="w")
            items = r.get("items", r.get("category",""))
            if items and len(items) > 80:
                items = items[:77] + "..."
            tk.Label(card, text=items, font=("Segoe UI",8), bg=CARD, fg=TEXTSUB, wraplength=260, justify="left").pack(anchor="w", pady=(4,0))

            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", pady=(6,0))

            def make_open(url=r.get("bid_url")):
                return (lambda: webbrowser.open(url)) if url else (lambda: None)

            if r.get("bid_url"):
                self._btn(row, "🌐", make_open(r.get("bid_url")), bg=PANEL).pack(side="left")

            def move_next(rec=r):
                # cycle Evaluating -> To Be Filed -> Filed
                cur = (rec.get("filing_status") or "").strip().lower()
                if cur == "evaluating":
                    rec["filing_status"] = "To Be Filed"
                elif cur == "filed":
                    rec["filing_status"] = "Evaluating"
                else:
                    rec["filing_status"] = "Filed"
                try:
                    db.save_all_tenders(self._records)
                except Exception:
                    pass
                self._update_kanban()

            self._btn(row, "Move", move_next, bg=ACCENT2).pack(side="right")
