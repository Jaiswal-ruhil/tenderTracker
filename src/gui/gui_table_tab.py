# Backward-compatible adapter for Table Tab Mixin

import tkinter as tk
from components.date_picker import DatePickerPopup
from components.table_tab import TableTab

class TableTabMixin:
    def _build_table_tab(self):
        # Instantiate the TableTab component and pack it
        self.table_tab = TableTab(self.tab_table, self)
        self.table_tab.pack(fill="both", expand=True)

        # Expose child widgets/variables on TenderApp namespace for backward compatibility
        self.search_var = self.table_tab.search_var
        self.search_ent = self.table_tab.search_ent
        self.view_var = self.table_tab.view_var
        self.status_view_var = self.table_tab.status_view_var
        self.date_filter_preset_var = self.table_tab.date_filter_preset_var
        self.date_filter_type_var = self.table_tab.date_filter_type_var
        self.date_from_var = self.table_tab.date_from_var
        self.date_to_var = self.table_tab.date_to_var
        self.tv = self.table_tab.tv
        self.custom_date_frame = self.table_tab.custom_date_frame
        
    def _refresh_table_view(self):
        self.table_tab.refresh_table_view()
        
    def _get_tender_status(self, rec, inc_kws, exc_kws):
        return self.table_tab.get_tender_status(rec, inc_kws, exc_kws)
        
    def _is_bid_in_dont_wants(self, bid_no_or_id):
        return self.table_tab.is_bid_in_dont_wants(bid_no_or_id)

    def _show_datepicker(self, button, var):
        self.table_tab._show_datepicker(button, var)

    def _cancel_edit(self, event=None):
        self.table_tab.table_view.cancel_edit(event)

    def _open_associated_pdf(self):
        self.table_tab.open_associated_pdf()

    def _link_associated_pdf(self):
        self.table_tab.link_associated_pdf()

    def _unlink_associated_pdf(self):
        self.table_tab.unlink_associated_pdf()

    def _start_filing_process(self):
        self.table_tab.start_filing_process()

    def _open_tender_url(self):
        self.table_tab.open_tender_url()

    def _copy_bid_number(self):
        self.table_tab.copy_bid_number()

    def _save_selected(self):
        self.table_tab.save_selected()

    def _mark_selected_want(self):
        self.table_tab.mark_selected_want()

    def _mark_want_and_learn(self):
        self.table_tab.mark_want_and_learn()

    def _mark_selected_dont_want(self):
        self.table_tab.mark_selected_dont_want()

    def _reset_selected_tag(self):
        self.table_tab.reset_selected_tag()

    def _set_selected_filing_status(self, status):
        self.table_tab.set_selected_filing_status(status)

    def _apply_column_visibility(self):
        self.table_tab.apply_column_visibility()

    def _show_column_selector(self):
        self.table_tab.show_column_selector()

    def _copy_table_output(self):
        self.table_tab.copy_table_output()

    def _tv_insert(self, rec):
        return self.table_tab.table_view.tv_insert(rec)

    def _refresh_alt(self):
        self.table_tab.table_view.refresh_alt()

    # ── Keyboard Shortcuts and Helpers ─────────────────────────────────────
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

    def _del_sel(self):
        self.table_tab.del_sel()
