import unittest
import sys
import os

# Add src/core to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "core")))

import tender_tools

class TestTenderTools(unittest.TestCase):

    def setUp(self):
        self.sample_pdf_text = """
        Bid Details
        Bid Number: GEM/2026/B/9520877
        Dated: 05-07-2026
        Bid Start Date: 05-07-2026
        Bid End Date/Time: 20-07-2026 15:00:00
        Bid Opening Date/Time: 20-07-2026 15:30:00
        Estimated Bid Value: 1,500,000
        Ministry/State Name: Ministry of Mines
        Department Name: Department of Geological Survey
        Organisation Name: Geological Survey of India
        Office Name: Northern Region HQ

        EMD Detail
        Advisory Bank: State Bank of India
        EMD Amount: 30,000

        ePBG Detail
        Required: Yes
        Advisory Bank: State Bank of India
        ePBG Percentage: 5.00
        Duration of ePBG (Months): 12

        Item Details
        Item Category: Heavy Industrial Electric Motor
        Total Quantity: 5
        Contract Duration: 90 Days
        Evaluation Method: Total Value Wise Evaluation
        Type of Bid: Two Packet Bid
        Bid to RA enabled: Yes

        Consignees/Reporting Officer / Address
        S.No, Consignee/Reporting Officer, Address, Quantity, Delivery Days
        1, Ram Kumar, 226001, Kisan Mill, Lucknow, 5, 90

        Bill of Quantities / Schedule of Requirement
        SNo Item Description Qty Unit
        1 Three Phase Slipring Motor 11KW 5 Nos
        """

    def test_extract_bid_metadata(self):
        res = tender_tools.extract_bid_metadata(self.sample_pdf_text)
        self.assertEqual(res.get("bid_no"), "GEM/2026/B/9520877")
        self.assertEqual(res.get("bid_url"), "https://bidplus.gem.gov.in/showbidDocument/9520877")
        self.assertEqual(res.get("start_date"), "05-07-2026")
        self.assertEqual(res.get("end_date"), "20-07-2026 15:00:00")
        self.assertEqual(res.get("bid_opening"), "20-07-2026 15:30:00")
        self.assertEqual(res.get("est_value"), "1500000")

    def test_extract_department_info(self):
        res = tender_tools.extract_department_info(self.sample_pdf_text)
        self.assertEqual(res.get("ministry"), "Ministry of Mines")
        self.assertEqual(res.get("dept"), "Department of Geological Survey")
        self.assertEqual(res.get("organisation"), "Geological Survey of India")
        self.assertEqual(res.get("office"), "Northern Region HQ")

    def test_extract_eligibility_criteria(self):
        text = """
        Minimum Average Annual Turnover: 5 Lakhs
        Years of Past Experience: 2 Years
        MII Compliance: Yes
        MSE Purchase Preference: Yes
        MSE Relaxation: No
        Startup Relaxation: No
        """
        res = tender_tools.extract_eligibility_criteria(text)
        self.assertEqual(res.get("min_turnover"), "5 Lakhs")
        self.assertEqual(res.get("exp_years"), "2 Years")
        self.assertEqual(res.get("mii"), "Yes")
        self.assertEqual(res.get("mse_pref"), "Yes")
        self.assertEqual(res.get("mse_relax"), "No")
        self.assertEqual(res.get("startup_relax"), "No")

    def test_extract_financial_security(self):
        res = tender_tools.extract_financial_security(self.sample_pdf_text)
        self.assertEqual(res.get("emd"), "Yes")
        self.assertEqual(res.get("emd_amount"), "30000")
        self.assertEqual(res.get("epbg"), "Yes")

    def test_extract_item_details(self):
        res = tender_tools.extract_item_details(self.sample_pdf_text)
        self.assertEqual(res.get("category"), "Heavy Industrial Electric Motor")
        self.assertEqual(res.get("items"), "Heavy Industrial Electric Motor")
        self.assertEqual(res.get("quantity"), "5")
        self.assertEqual(res.get("contract_dur"), "90 Days")
        self.assertEqual(res.get("eval_method"), "Total Value Wise Evaluation")
        self.assertEqual(res.get("bid_type"), "Two Packet Bid")
        self.assertEqual(res.get("bid_to_ra"), "Yes")

    def test_extract_consignee_location(self):
        res = tender_tools.extract_consignee_location(self.sample_pdf_text)
        self.assertEqual(res.get("location"), "226001, Kisan Mill, Lucknow")

    def test_extract_boq_table(self):
        res = tender_tools.extract_boq_table(self.sample_pdf_text)
        boq = res.get("boq", [])
        self.assertTrue(len(boq) >= 1)
        self.assertEqual(boq[0].get("item"), "Three Phase Slipring Motor 11KW")
        self.assertEqual(boq[0].get("qty"), "5")
        self.assertEqual(boq[0].get("unit"), "Nos")

    def test_search_pdf_section(self):
        text = """
        Technical Specifications
        The motor must be copper wound and IP55 rated.
        Section 2
        Next section content...
        """
        res = tender_tools.search_pdf_section(text, "Technical Specifications")
        self.assertIn("copper wound", res.get("content", ""))
        self.assertNotIn("Next section content", res.get("content", ""))

if __name__ == '__main__':
    unittest.main()
