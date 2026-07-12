# Backward-compatible adapter for Analytics Tab Mixin

from components.analytics_tab import AnalyticsTab

class AnalyticsTabMixin:
    def _build_analytics_tab(self):
        # Instantiate the AnalyticsTab component
        self.analytics_tab = AnalyticsTab(self.tab_analytics, self)
        self.analytics_tab.pack(fill="both", expand=True)

        # Expose widgets on TenderApp namespace for backward compatibility
        self.lbl_total_tenders = self.analytics_tab.lbl_total_tenders
        self.lbl_matching_wants = self.analytics_tab.lbl_matching_wants
        self.lbl_filtered_dont_wants = self.analytics_tab.lbl_filtered_dont_wants
        self.lbl_not_filed = self.analytics_tab.lbl_not_filed
        self.lbl_firm_matched = self.analytics_tab.lbl_firm_matched

    def _update_analytics(self):
        self.analytics_tab.update_analytics()

    def _redraw_chart(self):
        self.analytics_tab.redraw_chart()

    def _redraw_firm_chart(self):
        self.analytics_tab.redraw_firm_chart()

    def _show_all_tenders(self):
        self.analytics_tab.show_all_tenders()

    def _show_matching_wants(self):
        self.analytics_tab.show_matching_wants()

    def _show_filtered_dont_wants(self):
        self.analytics_tab.show_filtered_dont_wants()

    def _show_not_filed_wants(self):
        self.analytics_tab.show_not_filed_wants()

    def _show_firm_matched(self):
        self.analytics_tab.show_firm_matched()

    def _filter_by_ministry(self, name):
        self.analytics_tab._filter_by_ministry(name)

    def _filter_by_firm(self, name):
        self.analytics_tab._filter_by_firm(name)
