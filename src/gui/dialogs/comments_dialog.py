# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox

# Local imports
from config import BG, PANEL, CARD, ACCENT2, TEXT, FT, FL
import db

class CommentsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grab_set()
        self.transient(parent)
        self.configure(bg=BG)
        self.resizable(False, False)

        sel = self.parent.tv.selection()
        if not sel:
            messagebox.showwarning("No Rows Selected", "Please select a tender to view or add comments.", parent=self)
            self.destroy()
            return

        iid = sel[0]
        bid_no = self.parent.tv.set(iid, "bid_no")
        if not bid_no:
            self.destroy()
            return

        self.title(f"Tender Comments - {bid_no}")

        # Find the record
        rec = None
        for r in self.parent._records:
            if r.get("bid_no") == bid_no:
                rec = r
                break
        
        if not rec:
            self.destroy()
            return

        current_comments = rec.get("comments") or ""

        x = parent.winfo_x() + (parent.winfo_width() - 480) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 320) // 2
        self.geometry(f"480x320+{max(0, x)}+{max(0, y)}")

        tk.Label(self, text=f"Comments for {bid_no}", font=FT, bg=BG, fg=TEXT).pack(pady=(12, 10))

        btn_fr = tk.Frame(self, bg=BG)
        btn_fr.pack(fill="x", side="bottom", pady=12, padx=20)

        txt_frame = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground="#30363D")
        txt_frame.pack(fill="both", expand=True, padx=20, pady=6)

        comments_text = tk.Text(txt_frame, bg=CARD, fg=TEXT, insertbackground=TEXT,
                                relief="flat", font=FL, wrap="word", highlightthickness=0,
                                padx=8, pady=8)
        comments_text.pack(fill="both", expand=True)
        comments_text.insert("1.0", current_comments)

        def save_comments():
            comments = comments_text.get("1.0", "end-1c").strip()
            # Save to database
            db.upsert_tender_field(bid_no, "comments", comments)
            
            # Clear embedding to trigger re-embedding with new comments
            db.upsert_tender_field(bid_no, "embedding", None)
            
            # Update local record
            rec["comments"] = comments
            rec["embedding"] = None
            
            # Trigger background embedding in background thread
            try:
                import vector_search
                vector_search.start_background_embedding_worker()
            except Exception as ex:
                self._log("warn", f"Could not restart background embedder: {ex}")
            
            # Run active learning to immediately apply any comment rules
            try:
                db.apply_active_learning_from_comments()
            except Exception as al_err:
                self._log("warn", f"Could not apply active learning: {al_err}")
                
            # Reload all UI and data from database
            self.parent._reload()
                
            self._log("ok", f"Saved comments for bid {bid_no}. Regenerating embedding in background.")
            self.destroy()

        self._btn(btn_fr, "Save Comments", save_comments, bg=ACCENT2).pack(side="right", padx=4)
        self._btn(btn_fr, "Cancel", self.destroy, bg=CARD).pack(side="right", padx=4)

    def _btn(self, *args, **kwargs):
        return self.parent._btn(*args, **kwargs)

    def _log(self, *args, **kwargs):
        return self.parent._log(*args, **kwargs)
