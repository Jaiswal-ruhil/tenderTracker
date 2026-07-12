# TenderTracker MCP Setup

TenderTracker has three focused MCP servers. This keeps tender search, analysis, and filing preparation independently deployable and lets an agent receive only the capabilities it needs.

| Server | Purpose | stdio command |
| --- | --- | --- |
| `catalog` | Retrieve, search, and update tender records | `python mcp_runner.py --server catalog` |
| `analysis` | Parse, classify, and product-match tenders | `python mcp_runner.py --server analysis` |
| `filing` | Create a filing pack and checklist; never submits a bid | `python mcp_runner.py --server filing` |

The former all-in-one server remains available as `--server legacy` for existing clients.

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
