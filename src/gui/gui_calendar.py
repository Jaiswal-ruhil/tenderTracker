# Backward-compatible adapter for Calendar Tab Mixin

from components.calendar_tab import CalendarTab

class CalendarTabMixin:
    def _build_calendar_tab(self):
        # Instantiate the CalendarTab component
        self.calendar_tab = CalendarTab(self.tab_calendar, self)
        self.calendar_tab.pack(fill="both", expand=True)

        # Expose widgets/variables on TenderApp namespace for backward compatibility
        self.cal_month_lbl = self.calendar_tab.cal_month_lbl
        self.cal_sel_date_lbl = self.calendar_tab.cal_sel_date_lbl
        self.cal_details_fr = self.calendar_tab.cal_details_fr
        # cal_day_frames is already on self (TenderApp)

    def _cal_prev_month(self):
        self.calendar_tab.cal_prev_month()

    def _cal_next_month(self):
        self.calendar_tab.cal_next_month()

    def _parse_date_str(self, date_str):
        return self.calendar_tab._parse_date_str(date_str)

    def _get_events_for_date(self, target_date, inc_kws=None, exc_kws=None):
        return self.calendar_tab.get_events_for_date(target_date, inc_kws, exc_kws)

    def _update_calendar(self):
        self.calendar_tab.update_calendar()

    def _select_date(self, target_date):
        self.calendar_tab.select_date(target_date)

    def _update_details(self):
        self.calendar_tab.update_details()

    def _locate_in_table(self, bid):
        self.calendar_tab.locate_in_table(bid)
