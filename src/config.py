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

FH = ("Consolas", 9)
FB = ("Segoe UI", 10)
FL = ("Segoe UI", 9)
FT = ("Segoe UI", 12, "bold")

# Table columns configuration
TV_COLS = [
    ("bid_no",       "Bid No",            180),
    ("ministry",     "Ministry",          160),
    ("dept",         "Department",        180),
    ("organisation", "Organisation",      140),
    ("category",     "Category",          120),
    ("items",        "Items",             160),
    ("quantity",     "Qty",                55),
    ("location",     "Consignee/Location",150),
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
    ("bid_opening",  "Bid Opening",       130),
    ("start_date",   "Start Date",        130),
    ("end_date",     "End Date",          130),
    ("filing_status", "Filing Status",    110),
    ("tags",         "Tags",              120),
    ("remarks",      "Remarks",           120),
]
TV_IDS = [c[0] for c in TV_COLS]

# Intelligent Category Mapping Configuration
CATEGORY_MAPPING = [
    (["cane", "transport"], "Cane Transportation"),
    (["cane", "loader"], "Cane Loading/Harvesting"),
    (["loader", "loading"], "Loading Services"),
    (["computer", "laptop", "desktop", "monitor", "ups", "server", "software"], "IT & Computers"),
    (["printer", "scanner", "photocopier", "cartridge"], "Office & Printing"),
    (["sugar", "mill", "chini"], "Sugar Mill Operations"),
    (["manpower", "security", "guard", "staff"], "Manpower & Security"),
]
