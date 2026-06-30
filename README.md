# GeM Tender Tracker

A modular, high-performance desktop application built in Python (Tkinter) to parse, scrape, and catalog Government of India (GeM) Tenders. The app supports parsing copy-pasted web text, crawling detail pages via Selenium, and extracting data from local GeM Bidding PDF files.

---

## Key Features

* **Sleek Custom Desktop UI**: Modern dark-themed dashboard with HSL panels, interactive data tables (Treeview), styled progress meters, and dynamic action logs.
* **SQLite Database Backend**: Self-healing SQLite3 database (`tenders_db.db`) replacing flat JSON files, featuring transaction timeouts, concurrent lock protection, and automatic backward-compatible migration of legacy JSON records.
* **Concurrent Ingestion Engine**: Parallel pipelines using `ThreadPoolExecutor` (max 3 workers for PDF downloads, max 2 workers for Selenium scraping) to optimize crawling speeds without blocking the UI.
* **Advanced Logical Rules Filter**: Advanced boolean matching (`AND`, `OR`, `NOT` grouping with parentheses) and regular expressions prefixed with `rx:` to refine "Want" alerts.
* **Visual Analytics Hub**: Interactive dashboard tab rendering custom-drawn ministry bar charts, deadline status progress, and metric status cards.
* **Custom Toast Alerts**: Border-accented bottom-right notifications that fade out smoothly via alpha blending when new matching tenders are parsed or when crawls complete.
* **Tags System & Multi-Tag Selection**: A custom-made tags manager allows defining, deleting, and assigning multiple color-coded tag labels to tenders.
* **Export & Copy Table**: Export formatted Excel spreadsheets (e.g. `Tenders_FY_2026-27.xlsx`) or copy table selections directly to the clipboard in tab-separated (TSV) values.

---

## Application Flow Diagram

Below is the workflow showing how inputs are processed, parsed, filtered, stored, and displayed within the application:

```mermaid
flowchart TD
    subgraph Input & Parsing
        A[User Pastes Text, URLs, or PDF Paths] --> B[ThreadPoolExecutor split & process blocks]
        B --> C{Is PDF Path?}
        C -->|Yes| D[Parse local PDF file]
        C -->|No| E[Parse text metadata block]
    end

    subgraph Database Check & Fetching
        D & E --> F{Is in SQLite 'Don't Wants'?}
        F -->|Yes| G[Skip block / Ignore]
        F -->|No| H{Has full details?}
        H -->|Yes| I[Use parsed details]
        H -->|No| J[Concurrent Selenium Crawl / PDF download]
    end

    subgraph Storage & Filtering
        I & J --> K[Upsert to SQLite Database]
        K --> L[Apply Advanced Filter Rules: Regex & Boolean AND/OR/NOT]
        L --> M{Matches 'Wants'?}
        M -->|Yes| N[Trigger Custom Match Toast Notification]
        M -->|No| O[Save as Don't Want / Hide in Table View]
    end

    subgraph UI & Output
        N & O --> P[Update UI Views: Table, Calendar, Matrix, Analytics]
        P --> Q[Copy Rows to Clipboard / Export formatted Excel]
    end
```

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
