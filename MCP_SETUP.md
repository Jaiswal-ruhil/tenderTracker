# TenderTracker Model Context Protocol (MCP) Server Setup

This project now includes a built-in Model Context Protocol (MCP) server that exposes its core parsing, scraping, and vector search features as tools for AI models. By configuring this MCP server in your AI client, the AI can read, parse, scrape, and semantically search tenders directly.

## Available Tools

1. `list_tenders()`: List all tenders stored in the SQLite database.
2. `search_tenders_semantically(query, limit)`: Performs semantic vector search on the tenders database.
3. `parse_tender_text(text)`: Parses copy-pasted tender text block from GeM and extracts structured fields.
4. `parse_tender_pdf(pdf_path)`: Reads a PDF file, extracts its text, and parses it into structured fields.
5. `scrape_tender_url(url, headless)`: Scrapes a GeM tender detail page by URL.
6. `add_tender_to_db(record)`: Upserts a tender record in the SQLite database.
7. `update_tender_field(bid_no, field, value)`: Updates a single field (like status, remarks, tags) of an existing tender.
8. `rebuild_search_index()`: Rebuilds the FAISS / Annoy vector search index.

---

## Configuration

To connect this MCP server to an AI client (such as Claude Desktop, Cursor, or LibreChat), configure it to execute the `mcp_runner.py` script.

### 1. Claude Desktop Configuration

Open your Claude Desktop configuration file (typically located at `%APPDATA%\Claude\claude_desktop_config.json` on Windows) and add the following entry under `mcpServers`:

```json
{
  "mcpServers": {
    "tendertracker": {
      "command": "python",
      "args": [
        "D:/tenderTracker/mcp_runner.py"
      ]
    }
  }
}
```

*Note: Replace `D:/tenderTracker` with the absolute path to your project folder if it is located elsewhere.*

### 2. Cursor Configuration

To configure it in **Cursor Settings**:
1. Open Cursor Settings -> Features -> MCP.
2. Click **+ Add New MCP Server**.
3. Fill in the details:
   - **Name**: `TenderTracker`
   - **Type**: `command`
   - **Command**: `python D:/tenderTracker/mcp_runner.py`
4. Click **Save**.

---

## Technical Details

- The server uses the official Anthropic `mcp` Python library.
- It automatically detects the virtual environment (`.venv`) and runs inside it to ensure all dependencies (`faiss`, `pypdf`, `selenium`, etc.) are resolved correctly.
- It operates over standard input/output (`stdio`), which is the standard transport protocol for MCP servers.
