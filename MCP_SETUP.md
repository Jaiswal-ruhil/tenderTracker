# TenderTracker MCP Setup

TenderTracker has three focused MCP servers. This keeps tender search, analysis, and filing preparation independently deployable and lets an agent receive only the capabilities it needs.

| Server | Purpose | stdio command |
| --- | --- | --- |
| `catalog` | Retrieve, search, and update tender records with pagination support | `python mcp_runner.py --server catalog` |
| `analysis` | Parse, classify, and AI-enhanced product-match tenders | `python mcp_runner.py --server analysis` |
| `filing` | Create filing pack with GEM validation, AI matching, and compliance checks | `python mcp_runner.py --server filing` |

The former all-in-one server remains available as `--server legacy` for existing clients.

## Enhanced Capabilities

### Catalog Server
- **Pagination support**: `search_bids` now accepts `limit` and `offset` parameters for handling large datasets efficiently
- **Optimized queries**: Uses database-level pagination to reduce memory usage

### Analysis Server
- **AI-enhanced product matching**: `match_company_products` now uses similarity scoring with confidence metrics
- **Match details**: Returns match type (keyword vs AI similarity) and confidence scores for each match
- **Better accuracy**: Fallback to AI similarity when keyword matching fails

### Filing Server
- **GEM compliance validation**: Automatic validation of documents for file size (10MB), page count (100), and integrity
- **AI-enhanced document matching**: Multi-method similarity scoring with confidence thresholds
- **Validation reports**: Generates detailed validation reports for all copied documents
- **GEM requirements mapping**: Maps required documents to GEM portal upload fields
- **Processing statistics**: Tracks and returns detailed statistics about the filing process
- **New tools**:
  - `validate_document_integrity`: Validate individual documents for GEM compliance
  - `get_gem_requirements_mapping`: Get GEM portal document requirements for a tender

## Claude Desktop configuration

Add only the servers appropriate for the agent. For example, a search agent should receive the catalog service but not the filing service:

```json
{
  "mcpServers": {
    "tendertracker-catalog": {
      "command": "python",
      "args": [
        "D:/tenderTracker/mcp_runner.py",
        "--server",
        "catalog"
      ]
    }
  }
}
```

## Cursor configuration

Create a command MCP server with this command:

```text
python D:/tenderTracker/mcp_runner.py --server catalog
```

Repeat with `analysis` or `filing` only where that access is required.

## n8n

n8n's MCP Client Tool connects to SSE endpoints. Start the three services with `--transport sse`; the endpoint addresses and the required human approval gate are in [n8n/README.md](n8n/README.md).

The servers use the Python `mcp` library and support stdio, SSE, and streamable HTTP transports. The n8n integration should use SSE.
