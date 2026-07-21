import os

# Theme Constants (overridable via TT_* environment variables)
BG      = os.getenv("TT_BG", "#0D1117")
PANEL   = os.getenv("TT_PANEL", "#161B22")
CARD    = os.getenv("TT_CARD", "#21262D")
ACCENT  = os.getenv("TT_ACCENT", "#238636")
ACCENT2 = os.getenv("TT_ACCENT2", "#1F6FEB")
MUTED   = os.getenv("TT_MUTED", "#8B949E")
TEXT    = os.getenv("TT_TEXT", "#E6EDF3")
TEXTSUB = os.getenv("TT_TEXTSUB", "#7D8590")
SUCCESS = os.getenv("TT_SUCCESS", "#3FB950")
ERR     = os.getenv("TT_ERR", "#F85149")
WARN    = os.getenv("TT_WARN", "#D29922")
SEL_BG  = os.getenv("TT_SEL_BG", "#1F6FEB")

# Urgency row colors (used for deadline-based row highlighting)
URGENT_BG  = os.getenv("TT_URGENT_BG", "#3B1A1A")   # closing in <=24h — deep red
WARN_BG    = os.getenv("TT_WARN_BG", "#2E2300")     # closing in <=72h — deep amber
CLOSED_FG  = os.getenv("TT_CLOSED_FG", "#3D4450")   # already closed — greyed

FONT_MONO = os.getenv("TT_FONT_MONO", "Consolas")
FONT_MAIN = os.getenv("TT_FONT_MAIN", "Segoe UI")

FH = (FONT_MONO, 10)
FB = (FONT_MAIN, 10)
FL = (FONT_MAIN, 9)
FT = (FONT_MAIN, 12, "bold")

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
