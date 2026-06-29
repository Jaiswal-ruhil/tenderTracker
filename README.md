# GeM Tender Tracker

A modular, high-performance desktop application built in Python (Tkinter) to parse, scrape, and catalog Government of India (GeM) Tenders. The app supports parsing copy-pasted web text, crawling detail pages via Selenium, and extracting data from local GeM Bidding PDF files.

---

## Key Features

* **Sleek Custom Desktop UI**: Modern dark-themed dashboard with HSL panels, interactive data tables (Treeview), styled progress meters, and dynamic action logs.
* **Local PDF Data Extraction**: Paste a path or drag-and-drop a GeM PDF document directly into the paste box to automatically parse and map **21 detailed fields** (using page-extraction fallbacks like Consignee tables).
* **Selenium Scraper Fallback**: Autodetects bid page URLs and crawls them in the background using Selenium Chrome Webdriver to fetch organizational details.
* **Smart Row De-duplication**: Auto-merges incoming rows. If a tender ID already exists, it improves the entry by only populating missing cells instead of creating duplicate records.
* **Excel Exporting**: Saves parsed tenders to a structured, formatted Excel sheet named after the corresponding financial year (e.g., `Tenders_FY_2026-27.xlsx`).
* **CI/CD Pipelines**: Integrated GitHub Actions workflow to build, test, sign, and release standalone Windows binaries automatically.
* **Pre-commit Safeguards**: Custom Git pre-commit hooks that run the test suite and enforce checks prior to allowing a commit.

---

## Directory Structure

```text
tenderTracker/
├── .github/workflows/
│   └── build.yml             # GitHub Actions CI build & release pipeline
├── .git/hooks/
│   └── pre-commit            # Local git hook running unit tests
├── src/                      # Application source modules
│   ├── config.py             # Theme styles, fonts, and Treeview layout
│   ├── excel.py              # Financial year and Excel workbook helpers
│   ├── gui.py                # Main UI layout, event loop, and workers
│   ├── parser.py             # Clipboard block and PDF parsing logic
│   └── scraper.py            # Selenium webdriver crawler logic
├── tests/
│   └── test_parser.py        # Comprehensive test suite covering parser regexes
├── sample/
│   └── GeM-Bidding-9520877.pdf # Sample GeM bidding PDF for testing
├── main.py                   # Entry point launcher script
├── requirements.txt          # Third-party Python dependencies
└── README.md                 # Project documentation
```

---

## Setup & Running Locally

### Prerequisites
* Python 3.11+
* Google Chrome (required for the Selenium detail crawler)

### Installation
1. Clone the repository and navigate to the project directory:
   ```bash
   cd tenderTracker
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Run the App
```bash
python main.py
```

### Run Unit Tests
```bash
python -m unittest tests/test_parser.py
```

---

## Standalone Executable Compilation

To compile a standalone, self-signed Windows executable (`TenderTracker.exe`) containing all Webdriver and styling resources:

```bash
python -m PyInstaller --onefile --name "TenderTracker" --paths src --collect-all selenium --collect-all webdriver_manager --hidden-import pandas --hidden-import openpyxl --hidden-import openpyxl.styles --hidden-import openpyxl.utils --noconsole main.py
```

The compiled binary will be located inside the `dist/` directory.

---

## Usage Guide

1. **Launch the App**: Open `TenderTracker.exe` (or run `python main.py`).
2. **Configure Save Location**: Click **Browse** at the top to select your preferred directory for saving the Excel sheets.
3. **Parse Tenders**:
   * **Option A**: Copy a GeM bidding block from the website and paste it into the textbox.
   * **Option B**: Copy the path to a local GeM Bidding PDF file (e.g., `sample\GeM-Bidding-9520877.pdf`) and paste it into the textbox.
   * Click **1. Parse Blocks**.
4. **Scrape Web Details (Optional)**: Select one or more rows in the table and click **2. Fetch Details (Selenium)** to fetch missing organizational or buyer metadata.
5. **Save to Excel**: Click **Save Selected to Excel** to log them into your local spreadsheet workbook.
