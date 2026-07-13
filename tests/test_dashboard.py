import os
import unittest
from unittest.mock import MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'gui'))

from components.dashboard_tab import DashboardTab

class TestDashboardTab(unittest.TestCase):
    def setUp(self):
        self.app = MagicMock()
        
    def test_dynamic_status_calculation(self):
        tab = object.__new__(DashboardTab)
        tab.app = self.app
        
        # Test Dynamic status calculation
        import datetime
        from datetime import date
        today_str = date.today().strftime("%d-%m-%Y")
        tomorrow_str = (date.today() + datetime.timedelta(days=1)).strftime("%d-%m-%Y")
        yesterday_str = (date.today() - datetime.timedelta(days=1)).strftime("%d-%m-%Y")
        
        self.assertEqual(tab._get_dynamic_status(today_str, "Evaluating"), "DUE TODAY")
        self.assertEqual(tab._get_dynamic_status(tomorrow_str, "Evaluating"), "DUE TOMORROW")
        self.assertEqual(tab._get_dynamic_status(yesterday_str, "Evaluating"), "MISSED")
        self.assertEqual(tab._get_dynamic_status(today_str, "Filed"), "FILED")
        self.assertEqual(tab._get_dynamic_status(today_str, "Not Filed"), "NOT FILED")

    def test_sugarmill_and_categories_lists(self):
        from components.dashboard_tab import CATEGORIES, SUGARMILLS
        self.assertIn("Nickel screen", CATEGORIES)
        self.assertIn("Motor", CATEGORIES)
        self.assertIn("NAJIBABAD", SUGARMILLS)
        self.assertIn("SAMPURNANAGAR", SUGARMILLS)

if __name__ == '__main__':
    unittest.main()
