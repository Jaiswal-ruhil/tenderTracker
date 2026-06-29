import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
import parser

class TestParser(unittest.TestCase):
    def test_split_blocks(self):
        text = """
        BID NO: GEM/2026/B/7526729
        Items: Item 1
        
        Bid Number: GEM/2026/B/7490294
        Items: Item 2
        """
        blocks = parser.split_blocks(text)
        self.assertEqual(len(blocks), 2)
        self.assertTrue(blocks[0].startswith("BID NO: GEM/2026/B/7526729"))
        self.assertTrue(blocks[1].startswith("Bid Number: GEM/2026/B/7490294"))

    def test_parse_one_standard(self):
        text = """
        BID NO: [GEM/2026/B/7526729](https://bidplus.gem.gov.in/showbiddocument/7526729)
        Items: Computer System
        Quantity: 58
        Department Name And Address:
        Ministry of Mines
        Start Date: 28-06-2026
        End Date: 29-06-2026 11:58 AM
        """
        r = parser.parse_one(text)
        self.assertEqual(r["bid_no"], "GEM/2026/B/7526729")
        self.assertEqual(r["bid_url"], "https://bidplus.gem.gov.in/showbiddocument/7526729")
        self.assertEqual(r["items"], "Computer System")
        self.assertEqual(r["quantity"], "58")
        self.assertEqual(r["dept"], "Ministry of Mines")
        self.assertEqual(r["start_date"], "28-06-2026")
        self.assertEqual(r["end_date"], "29-06-2026 11:58 AM")

    def test_parse_one_with_details(self):
        text = """
        BID NO: GEM/2026/B/7711387
        Ministry: Uttar Pradesh
        Organisation: Sugar Federation
        Office: Lucknow
        Category: Industrial Gas
        Estimated Value (Rs): 144000
        Evaluation Method: Total value wise
        Bid Type: Two Packet
        Bid to RA: No
        EMD Required: No
        ePBG Required: No
        MII Compliance: Yes
        MSE Purchase Preference: Yes
        MSE Relaxation: No
        Startup Relaxation: No
        Min Turnover (Lakhs): 1 Lakh
        Experience Required (Yrs): 2 Year
        Contract Duration: 1 Year
        """
        r = parser.parse_one(text)
        self.assertEqual(r["ministry"], "Uttar Pradesh")
        self.assertEqual(r["organisation"], "Sugar Federation")
        self.assertEqual(r["office"], "Lucknow")
        self.assertEqual(r["category"], "Industrial Gas")
        self.assertEqual(r["est_value"], "144000")
        self.assertEqual(r["eval_method"], "Total value wise")
        self.assertEqual(r["bid_type"], "Two Packet")
        self.assertEqual(r["bid_to_ra"], "No")
        self.assertEqual(r["emd"], "No")
        self.assertEqual(r["epbg"], "No")
        self.assertEqual(r["mii"], "Yes")
        self.assertEqual(r["mse_pref"], "Yes")
        self.assertEqual(r["mse_relax"], "No")
        self.assertEqual(r["startup_relax"], "No")
        self.assertEqual(r["min_turnover"], "1 Lakh")
        self.assertEqual(r["exp_years"], "2 Year")
        self.assertEqual(r["contract_dur"], "1 Year")

    def test_convert_pdf_text_to_markdown(self):
        pdf_text = """
        Bid Number: GEM/2026/B/7711387
        Item Category: Refilling of Industrial Gases
        Ministry/State Name: Uttar Pradesh
        Department Name: Uttar Pradesh Cooperative Sugar
        Organisation Name: N/a
        Office Name: Lucknow
        Dated: 25-06-2026
        Bid End Date/Time: 06-07-2026 15:00:00
        Estimated Bid Value in INR: 144000
        Evaluation Method: Total value wise evaluation
        Type of Bid: Two Packet Bid
        Bid to RA enabled: No
        EMD Detail Required: No
        ePBG Detail Required: No
        MII Compliance: Yes
        MSE Purchase Preference: Yes
        MSE Relaxation: No
        Startup Relaxation: No
        Minimum Average Annual Turnover: 1 Lakh (s)
        Years of Past Experience: 2 Year (s)
        Contract Period: 1 Year(s) 3 Day(s)
        Consignee
        Reporting/Officer
        Rahul Prakash
        Yadav
        Address Block Details
        700
        N/A
        """
        md = parser.convert_pdf_text_to_markdown(pdf_text)
        r = parser.parse_one(md)
        self.assertEqual(r["bid_no"], "GEM/2026/B/7711387")
        self.assertEqual(r["items"], "Refilling of Industrial Gases")
        self.assertEqual(r["quantity"], "700")
        self.assertEqual(r["ministry"], "Uttar Pradesh")
        self.assertTrue(r["dept"].startswith("Uttar Pradesh Cooperative Sugar"))
        self.assertEqual(r["organisation"], "N/a")
        self.assertEqual(r["office"], "Lucknow")
        self.assertEqual(r["start_date"], "25-06-2026")
        self.assertEqual(r["end_date"], "06-07-2026 15:00:00")
        self.assertEqual(r["est_value"], "144000")
        self.assertEqual(r["eval_method"], "Total value wise evaluation")
        self.assertEqual(r["bid_type"], "Two Packet Bid")
        self.assertEqual(r["bid_to_ra"], "No")
        self.assertEqual(r["emd"], "No")
        self.assertEqual(r["epbg"], "No")
        self.assertEqual(r["mii"], "Yes")
        self.assertEqual(r["mse_pref"], "Yes")
        self.assertEqual(r["mse_relax"], "No")
        self.assertEqual(r["startup_relax"], "No")
        self.assertEqual(r["min_turnover"], "1 Lakh (s)")
        self.assertEqual(r["exp_years"], "2 Year (s)")
        self.assertEqual(r["contract_dur"], "1 Year(s) 3 Day(s)")
        self.assertEqual(r["location"], "Address Block Details")

    def test_convert_pdf_text_to_markdown_with_pincode_address(self):
        pdf_text = """
        Bid Number: GEM/2026/B/9520877
        Item Category: Refilling of Industrial Gases
        Ministry/State Name: Uttar Pradesh
        Department Name: Uttar Pradesh Cooperative Sugar
        Organisation Name: N/a
        Office Name: Lucknow
        Dated: 25-06-2026
        Bid End Date/Time: 06-07-2026 15:00:00
        Consignee
        Reporting/Officer
        पता
        /Address
        संसाधनH क मा ा
        / Estimated
        Quantity (as
        per Unit of
        Measuremen
        t selected by
        buyer )
        अितTरd आव:यकता
        /Additional
        Requirement
        1
        Rahul Prakash
        Yadav
        276404,The Kisan Sahakari
        chini mill Sathiaon, Azamgarh
        (U.P) Pin Code -276406 GST
        NO-09AAAAK0204B1ZI Contact
        no -6389025002,9910729844
        700
        N/A
        """
        md = parser.convert_pdf_text_to_markdown(pdf_text)
        r = parser.parse_one(md)
        self.assertEqual(r["bid_no"], "GEM/2026/B/9520877")
        self.assertEqual(r["quantity"], "700")
        self.assertEqual(r["location"], "276404,The Kisan Sahakari chini mill Sathiaon, Azamgarh (U.P) Pin Code -276406 GST NO-09AAAAK0204B1ZI Contact no -6389025002,9910729844")

if __name__ == '__main__':
    unittest.main()
