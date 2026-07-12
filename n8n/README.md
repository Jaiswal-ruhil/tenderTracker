# TenderTracker n8n Agent

The n8n agent is intentionally an orchestrator: it calls the focused MCP services and never receives direct database or filesystem access.

## Start the MCP services

Run these in three separate PowerShell windows:

```powershell
python mcp_runner.py --server catalog --transport sse
python mcp_runner.py --server analysis --transport sse
python mcp_runner.py --server filing --transport sse
```

Their local SSE endpoints are:

| Service | Endpoint | Tools |
| --- | --- | --- |
| Catalog | `http://127.0.0.1:8101/sse` | Search, retrieve, and approved updates |
| Analysis | `http://127.0.0.1:8102/sse` | Extract, classify, and parse tender PDFs |
| Filing | `http://127.0.0.1:8103/sse` | Create filing pack and checklist |

If n8n runs in Docker on this Windows machine, use `http://host.docker.internal:<port>/sse` instead of `127.0.0.1`.

## Build the workflow

1. Add a **Chat Trigger** and an **AI Agent** node.
2. Attach your preferred chat model to the AI Agent.
3. Add three **MCP Client Tool** nodes, one per endpoint above, and connect each to the Agent's **Tool** connector. Select **None** authentication only while the services remain local.
4. For the Filing tool, include only `prepare_filing`. Keep it disconnected until after your review/approval branch is in place.
5. Add a **Respond to Chat** node after the agent.

Use this system message in the AI Agent:

```text
You are TenderTracker's bid-analysis assistant. Search and analyse tenders first.
Before updating a tender, state the intended field and value and obtain user confirmation.
Before calling prepare_filing, show the tender, chosen firm, and expected action, then obtain explicit confirmation.
Never claim a bid has been submitted: filing preparation does not upload, sign, or submit anything.
```

The MCP Client Tool supports selecting exactly which MCP tools the agent can access, so expose the smallest set needed for each workflow branch. The AI Agent requires at least one connected tool. See the [n8n MCP Client Tool docs](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.toolmcp/) and [AI Agent docs](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/).
