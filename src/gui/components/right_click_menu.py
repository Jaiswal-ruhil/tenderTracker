"""
right_click_menu.py
~~~~~~~~~~~~~~~~~~~
Unified context menu for table rows and table header columns in TenderTracker.
"""

import tkinter as tk
from tkinter import messagebox

from config import PANEL, TEXT, SEL_BG, FL, TV_COLS, ACCENT, ACCENT2, ERR


class TenderContextMenu:
    """
    Context menu for table rows and column headers.
    """
    def __init__(self, parent, app, table_tab):
        self.app = app
        self.table_tab = table_tab
        self.tv = table_tab.table_view.tv

        # Row Context Menu (Unified)
        self.row_menu = tk.Menu(parent, tearoff=0, bg=PANEL, fg=TEXT,
                                activebackground=SEL_BG, activeforeground=TEXT, font=FL)
        
        self.row_menu.add_command(label="📋 Start Filing Process", command=self.table_tab.start_filing_process)
        self.row_menu.add_command(label="🌐 Open Tender URL", command=self.table_tab.open_tender_url)
        self.row_menu.add_command(label="📝 Copy Bid Number", command=self.table_tab.copy_bid_number)
        self.row_menu.add_separator()
        
        self.row_menu.add_command(label="✅ Mark as Want (Keep)", command=self.table_tab.mark_selected_want)
        self.row_menu.add_command(label="✨ Mark as Want + Learn Keyword", command=self.table_tab.mark_want_and_learn)
        self.row_menu.add_command(label="🚫 Mark as Don't Want (Ignore)", command=self.table_tab.mark_selected_dont_want)
        self.row_menu.add_command(label="🔄 Reset Manual Tag", command=self.table_tab.reset_selected_tag)
        self.row_menu.add_command(label="🏷️ Manage Tags...", command=self.table_tab.show_tags_dialog)
        self.row_menu.add_command(label="💬 Add/Edit Comments...", command=self.table_tab.show_comments_dialog)
        
        # Batch operations submenu
        self.batch_menu = tk.Menu(self.row_menu, tearoff=0, bg=PANEL, fg=TEXT,
                                   activebackground=SEL_BG, activeforeground=TEXT, font=FL)
        self.batch_menu.add_command(label="✅ Batch Mark as Want", command=lambda: self.table_tab.batch_mark_want())
        self.batch_menu.add_command(label="🚫 Batch Mark as Don't Want", command=lambda: self.table_tab.batch_mark_dont_want())
        self.batch_menu.add_command(label="⏳ Batch Set Status: To Be Filed", command=lambda: self.table_tab.batch_set_status("To Be Filed"))
        self.batch_menu.add_command(label="🔍 Batch Set Status: Evaluating", command=lambda: self.table_tab.batch_set_status("Evaluating"))
        self.batch_menu.add_command(label="🎯 Batch Set Status: Filed", command=lambda: self.table_tab.batch_set_status("Filed"))
        self.batch_menu.add_command(label="🗑️ Batch Delete Selected", command=lambda: self.table_tab.batch_delete())
        self.row_menu.add_cascade(label="⚡ Batch Operations", menu=self.batch_menu)

        # Submenu for Filing Status
        self.status_menu = tk.Menu(self.row_menu, tearoff=0, bg=PANEL, fg=TEXT,
                                   activebackground=SEL_BG, activeforeground=TEXT, font=FL)
        self.status_menu.add_command(label="⏳ To Be Filed", command=lambda: self.table_tab.set_selected_filing_status("To Be Filed"))
        self.status_menu.add_command(label="🔍 Evaluating", command=lambda: self.table_tab.set_selected_filing_status("Evaluating"))
        self.status_menu.add_command(label="🎯 Filed", command=lambda: self.table_tab.set_selected_filing_status("Filed"))
        self.row_menu.add_cascade(label="📂 Set Filing Status", menu=self.status_menu)

        self.row_menu.add_separator()
        self.row_menu.add_command(label="🔗 Link PDF File...", command=self.table_tab.link_associated_pdf)
        self.row_menu.add_command(label="📖 Open Associated PDF", command=self.table_tab.open_associated_pdf)
        self.row_menu.add_command(label="❌ Unlink PDF File", command=self.table_tab.unlink_associated_pdf)
        self.row_menu.add_separator()
        self.row_menu.add_command(label="🗑️ Delete Selected", command=self.table_tab.del_sel)
        self.row_menu.add_command(label="🌐 Fetch Details (Selenium)", command=self.table_tab.do_fetch_sel)
        self.row_menu.add_command(label="📊 Save Selected to Excel", command=self.table_tab.save_selected)

    def show(self, event):
        region = self.tv.identify_region(event.x, event.y)
        
        # 1. Heading context menu
        if region == "heading":
            column_id = self.tv.identify_column(event.x)
            try:
                col_index = int(column_id[1:]) - 1
                display_cols = list(self.tv.cget("displaycolumns"))
                import db
                if display_cols == ["#all"] or not display_cols:
                    settings = db.load_settings()
                    visible = settings.get("visible_columns")
                    if not visible or not isinstance(visible, list):
                        display_cols = [c[0] for c in TV_COLS]
                    else:
                        display_cols = visible
                
                if 0 <= col_index < len(display_cols):
                    target_col = display_cols[col_index]
                    
                    hdr_menu = tk.Menu(self.tv, tearoff=0, bg=PANEL, fg=TEXT, activebackground=ACCENT, activeforeground=TEXT, font=FL)
                    
                    # Move Left
                    if col_index > 0:
                        def move_left():
                            cols = list(display_cols)
                            cols[col_index], cols[col_index - 1] = cols[col_index - 1], cols[col_index]
                            db.save_setting("visible_columns", cols)
                            self.table_tab.apply_column_visibility()
                        hdr_menu.add_command(label="◀ Move Left", command=move_left)
                    else:
                        hdr_menu.add_command(label="◀ Move Left", state="disabled")
                        
                    # Move Right
                    if col_index < len(display_cols) - 1:
                        def move_right():
                            cols = list(display_cols)
                            cols[col_index], cols[col_index + 1] = cols[col_index + 1], cols[col_index]
                            db.save_setting("visible_columns", cols)
                            self.table_tab.apply_column_visibility()
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
                        self.table_tab.apply_column_visibility()
                    hdr_menu.add_command(label="👁 Hide Column", command=hide_col)
                    
                    # Manage Columns
                    hdr_menu.add_command(label="⚙ Manage Columns...", command=self.table_tab.show_column_selector)
                    
                    hdr_menu.post(event.x_root, event.y_root)
                    return
            except Exception as e:
                self.app._log("err", f"Header menu error: {e}")

        # 2. Row context menu
        iid = self.tv.identify_row(event.y)
        if iid:
            if iid not in self.tv.selection():
                self.tv.selection_set(iid)
                
            # Dynamically set PDF options state
            bid_no = self.tv.set(iid, "bid_no")
            rec = None
            for r in self.app._records:
                if r.get("bid_no") == bid_no:
                    rec = r
                    break
            
            pdf_path = rec.get("pdf_path", "") if rec else ""
            if pdf_path:
                self.row_menu.entryconfigure("📖 Open Associated PDF", state="normal")
                self.row_menu.entryconfigure("❌ Unlink PDF File", state="normal")
            else:
                self.row_menu.entryconfigure("📖 Open Associated PDF", state="disabled")
                self.row_menu.entryconfigure("❌ Unlink PDF File", state="disabled")
                
            self.row_menu.post(event.x_root, event.y_root)
