import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'gui'))

import unittest
import parser

class TestParser(unittest.TestCase):
    def setUp(self):
        import db
        import shutil
        self.old_db = db.DB_FILE
        self.old_settings = db.SETTINGS_FILE
        db.DB_FILE = os.path.join(os.path.dirname(__file__), "test_parser_tenders_db.db")
        db.SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "test_parser_settings.json")
        if os.path.exists(db.DB_FILE):
            try: os.remove(db.DB_FILE)
            except: pass
        if os.path.exists(db.SETTINGS_FILE):
            try: os.remove(db.SETTINGS_FILE)
            except: pass
        shutil.copy(os.path.join(os.path.dirname(__file__), "test_settings.json"), db.SETTINGS_FILE)

    def tearDown(self):
        import db
        if os.path.exists(db.DB_FILE):
            try: os.remove(db.DB_FILE)
            except: pass
        if os.path.exists(db.SETTINGS_FILE):
            try: os.remove(db.SETTINGS_FILE)
            except: pass
        db.DB_FILE = self.old_db
        db.SETTINGS_FILE = self.old_settings

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

    def test_split_blocks_with_bid_number_at_start(self):
        # Test splitting when bid numbers appear at start without BID NO label
        text = """
GEM/2026/B/7690922  View Corrigendum/Representation
Items: TEFCSquirl Cage Inductionmotor
Quantity: 6
Department Name And Address: 
Cane Development (Ganna Vikas Vibhag) Department Uttar Pradesh
Start Date: 24-06-2026 9:49 AM
End Date:   16-07-2026 10:00 AM
        """
        blocks = parser.split_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertTrue(blocks[0].startswith("GEM/2026/B/7690922"))

    def test_split_blocks_with_preface(self):
        text = """
        C:/Users/pc/Downloads/GeM-Bidding-7593328.pdf
        C:/Users/pc/Downloads/GeM-Bidding-7612203.pdf
        
        BID NO: GEM/2026/B/7526729
        Items: Item 1
        """
        blocks = parser.split_blocks(text)
        self.assertEqual(len(blocks), 2)
        self.assertTrue("GeM-Bidding-7593328.pdf" in blocks[0])
        self.assertTrue(blocks[1].startswith("BID NO: GEM/2026/B/7526729"))

    def test_parse_one_standard(self):
        text = """
        BID NO: [GEM/2026/B/7526729](https://bidplus.gem.gov.in/showbidDocument/7526729)
        Items: Computer System
        Quantity: 58
        Department Name And Address:
        Ministry of Mines
        Start Date: 28-06-2026
        End Date: 29-06-2026 11:58 AM
        """
        r = parser.parse_one(text)
        self.assertEqual(r["bid_no"], "GEM/2026/B/7526729")
        self.assertEqual(r["bid_url"], "https://bidplus.gem.gov.in/showbidDocument/7526729")
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

    def test_parse_one_wildcard_bid_no(self):
        text = """
        BID NO: GEM/2026/B/7XXXXX6
        Items: Mat Procurements
        Quantity: 10
        """
        r = parser.parse_one(text)
        self.assertEqual(r["bid_no"], "GEM/2026/B/7XXXXX6")
        self.assertEqual(r["items"], "Mat Procurements")
        self.assertEqual(r["quantity"], "10")

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
        # No location expected: this test PDF has no pincode or real address
        # ("Address Block Details" is a column header, correctly skipped now)
        self.assertNotIn("location", r)

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
        # Location is enriched with district/state from PostalPincode API
        # (pincode 276404 → Azamgarh, Uttar Pradesh; "Azamgarh" already in string so only state appended)
        loc = r["location"]
        self.assertTrue(loc.startswith("276404,The Kisan Sahakari chini mill Sathiaon, Azamgarh"))
        self.assertIn("276404", loc)
        self.assertIn("Azamgarh", loc)

    def test_category_mapping_and_splitting(self):
        # 1. Test splitting and mapping in parse_one
        text = "Category: Electric Motor - 5HP 1440RPM"
        r = parser.parse_one(text)
        self.assertEqual(r["category"], "Motor")
        self.assertEqual(r["items"], "5HP 1440RPM")
        
        # 2. Test fallback and mapping in convert_pdf_text_to_markdown
        pdf_text = """
        Bid Number: GEM/2026/B/1111111
        Core
        Category
        Electric Motor - 5HP 1440RPM
        """
        md = parser.convert_pdf_text_to_markdown(pdf_text)
        r2 = parser.parse_one(md)
        self.assertEqual(r2["category"], "Motor")
        self.assertEqual(r2["items"], "5HP 1440RPM")

    def test_ni_screen_example(self):
        text = "Category: Ni Screen - 0.09Mm By 2.30Mmby .25 Mm , 0.06Mm By 2.20Mm By.27"
        r = parser.parse_one(text)
        self.assertEqual(r["category"], "Ni Screen")
        self.assertEqual(r["items"], "0.09Mm By 2.30Mmby .25 Mm , 0.06Mm By 2.20Mm By.27")

    def test_additional_categories(self):
        examples = [
            ("Category: Electric Motor - 5HP 1440RPM", "Motor", "5HP 1440RPM"),
            ("Category: Copper Armoured Cable - 4 Core 10 Sqmm", "Cable", "4 Core 10 Sqmm"),
            ("Category: Liquid Oxygen Gas - Refilling", "Oxygen", "Refilling"),
            ("Category: Argon Gas Cylinder", "Argon", "Argon Gas Cylinder"),
            ("Category: VFD Control Panel - 15KW", "VFD", "15KW"),
            ("Category: Gland Packing Jointing Sheet", "Packing Jointing", "Gland Packing Jointing Sheet"),
            ("Category: Welding Electrode - E6013 3.15mm", "Electrodes", "E6013 3.15mm"),
        ]
        for text, expected_cat, expected_item in examples:
            r = parser.parse_one(text)
            self.assertEqual(r["category"], expected_cat)
            self.assertEqual(r["items"], expected_item)

    def test_active_learning(self):
        import db
        # Backup old mappings to restore later
        old_mappings = db.load_settings().get("category_mappings")
        db.save_setting("category_mappings", [])
        
        try:
            parser.learn_category_mapping("Super Premium Safety Helmet", "Safety")
            mappings = db.load_settings().get("category_mappings", [])
            self.assertTrue(len(mappings) >= 1)
            
            safety_entry = None
            for m in mappings:
                if m["name"] == "Safety":
                    safety_entry = m
                    break
                    
            self.assertIsNotNone(safety_entry)
            self.assertIn("safety", safety_entry["keywords"])
        finally:
            if old_mappings is not None:
                db.save_setting("category_mappings", old_mappings)

    def test_parse_organization_spelling_variants(self):
        # 1. Test parsing with "Organisation Name" in PDF text
        pdf_text_s = "Organisation Name: Sugar Federation"
        md_s = parser.convert_pdf_text_to_markdown(pdf_text_s)
        self.assertIn("Organisation: Sugar Federation", md_s)
        r_s = parser.parse_one(md_s)
        self.assertEqual(r_s["organisation"], "Sugar Federation")
        
        # 2. Test parsing with "Organization Name" in PDF text
        pdf_text_z = "Organization Name: Sugar Federation"
        md_z = parser.convert_pdf_text_to_markdown(pdf_text_z)
        self.assertIn("Organisation: Sugar Federation", md_z)
        r_z = parser.parse_one(md_z)
        self.assertEqual(r_z["organisation"], "Sugar Federation")
        
        # 3. Test direct parsing with "Organization: Sugar Federation"
        r_direct = parser.parse_one("Organization: Sugar Federation")
        self.assertEqual(r_direct["organisation"], "Sugar Federation")

    def test_parse_bid_number_at_start_without_label(self):
        # Test parsing bid number that appears at start of text without "BID NO:" label
        # This reproduces the issue with GEM/2026/B/7690922
        text = """
GEM/2026/B/7690922  View Corrigendum/Representation
Items: TEFCSquirl Cage Inductionmotor
Quantity: 6
Department Name And Address: 
Cane Development (Ganna Vikas Vibhag) Department Uttar Pradesh
Start Date: 24-06-2026 9:49 AM
End Date:   16-07-2026 10:00 AM
        """
        r = parser.parse_one(text)
        self.assertEqual(r["bid_no"], "GEM/2026/B/7690922")
        self.assertEqual(r["items"], "TEFCSquirl Cage Inductionmotor")
        self.assertEqual(r["quantity"], "6")
        self.assertTrue(r["dept"].startswith("Cane Development"))
        self.assertEqual(r["start_date"], "24-06-2026 9:49 AM")
        self.assertEqual(r["end_date"], "16-07-2026 10:00 AM")

if __name__ == '__main__':
    unittest.main()
