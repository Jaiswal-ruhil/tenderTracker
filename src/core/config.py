# Theme Constants
BG      = "#0D1117"
PANEL   = "#161B22"
CARD    = "#21262D"
ACCENT  = "#238636"
ACCENT2 = "#1F6FEB"
MUTED   = "#8B949E"
TEXT    = "#E6EDF3"
TEXTSUB = "#7D8590"
SUCCESS = "#3FB950"
ERR     = "#F85149"
WARN    = "#D29922"
SEL_BG  = "#1F6FEB"

# Urgency row colors (used for deadline-based row highlighting)
URGENT_BG  = "#3B1A1A"   # closing in <=24h — deep red
WARN_BG    = "#2E2300"   # closing in <=72h — deep amber
CLOSED_FG  = "#3D4450"   # already closed — greyed

FH = ("Consolas", 9)
FB = ("Segoe UI", 10)
FL = ("Segoe UI", 9)
FT = ("Segoe UI", 12, "bold")

# Table columns configuration
TV_COLS = [
    ("bid_no",       "Bid No",            190),
    ("closing_in",   "Closing In",         88),
    ("ministry",     "Ministry",          160),
    ("dept",         "Department",        200),
    ("organisation", "Organisation",      160),
    ("category",     "Category",          180),
    ("items",        "Items",             340),
    ("quantity",     "Qty",                55),
    ("location",     "Consignee/Location",160),
    ("est_value",    "Est. Value (Rs)",   110),
    ("eval_method",  "Eval Method",       130),
    ("bid_type",     "Bid Type",          110),
    ("bid_to_ra",    "RA",                 45),
    ("emd",          "EMD",                45),
    ("epbg",         "ePBG",               45),
    ("mii",          "MII",                40),
    ("mse_pref",     "MSE Pref",           60),
    ("contract_dur", "Contract Dur",       90),
    ("min_turnover", "Turnover (L)",       80),
    ("exp_years",    "Exp Yrs",            55),
    ("bid_opening",  "Bid Opening",       140),
    ("start_date",   "Start Date",        100),
    ("end_date",     "End Date",          165),
    ("filing_status", "Filing Status",    145),
    ("tags",         "Tags",              120),
    ("remarks",      "Remarks",           140),
    ("matched_firm",  "Matched Firm",      120),
]
TV_IDS = [c[0] for c in TV_COLS]

# Intelligent Category Mapping Configuration
CATEGORY_MAPPING = [
    (["screen"], "Ni Screen"),
    (["motor"], "Motor"),
    (["cable"], "Cable"),
    (["oxygen"], "Oxygen"),
    (["argon"], "Argon"),
    (["vfd"], "VFD"),
    (["packing", "jointing"], "Packing Jointing"),
    (["electrode"], "Electrodes"),
    (["switch gear", "acb", "mccb"], "ACB/MCCB"),
]
