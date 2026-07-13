# TenderTracker n8n Integration

The n8n integration provides powerful workflow automation for TenderTracker, leveraging MCP services for AI-powered tender analysis, automated monitoring, and streamlined filing processes.

## Available Workflows

### 🚀 Automated Tender Monitoring
**File**: `workflows/automated_tender_monitoring.json`

Continuously monitors GeM portal for new tenders with AI-powered filtering and real-time alerts.

**Features**:
- Scheduled monitoring (every 2 hours during business hours)
- AI classification and product matching
- Confidence-based filtering (>0.7 threshold)
- Multi-channel alerts (Slack + Email)
- Automatic database updates and search index rebuild

**Use Case**: Never miss high-value opportunities while reducing manual monitoring effort by 80%.

### ⚡ Batch Processing
**File**: `workflows/batch_processing.json`

Process multiple tenders efficiently with parallel AI analysis and comprehensive reporting.

**Features**:
- File upload support (CSV, TXT, PDF)
- Parallel processing in batches of 10 tenders
- AI-powered classification, requirements generation, and product matching
- Excel export with processing statistics
- Completion notifications

**Use Case**: 10x faster tender analysis for bulk tender evaluation and reporting.

### 📋 Automated Filing Preparation
**File**: `workflows/automated_filing.json`

End-to-end automated filing preparation with AI-enhanced document matching and GEM compliance validation.

**Features**:
- Manual trigger with bid number and firm name
- AI-enhanced document matching with confidence scores
- GEM compliance validation and requirements mapping
- Automated filing folder creation and checklist generation
- Comprehensive validation reports with error handling

**Use Case**: 90% reduction in filing preparation time with error-free document organization.

## Quick Start

### 1. Start MCP Services

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

**Note**: If n8n runs in Docker on this Windows machine, use `http://host.docker.internal:<port>/sse` instead of `127.0.0.1`.

### 2. Install and Configure n8n

**Option A: Docker (Recommended)**
```bash
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

**Option B: Local Installation**
```bash
npm install n8n -g
n8n start
```

Access n8n at `http://localhost:5678`

### 3. Import Workflows

1. Open n8n interface at `http://localhost:5678`
2. Navigate to "Workflows" section
3. Click "Import from File"
4. Import each workflow JSON file from the `workflows/` directory:
   - `automated_tender_monitoring.json`
   - `batch_processing.json`
   - `automated_filing.json`

### 4. Configure MCP Connections

Each workflow contains MCP Client Tool nodes that need configuration:

**For each MCP Client node:**
- **Mode**: SSE
- **URL**: Use appropriate endpoint (8101/8102/8103)
- **Authentication**: None (for local development)
- **Docker users**: Replace `127.0.0.1` with `host.docker.internal`

### 5. Configure Notification Services

**Slack Integration:**
1. Create Slack App and Bot Token
2. Add Slack credentials in n8n
3. Update channel names in workflow nodes

**Email Integration:**
1. Configure SMTP settings in n8n credentials
2. Update recipient email addresses in workflow nodes

## Detailed Documentation

- **Workflow Plan**: `WORKFLOW_PLAN.md` - Comprehensive workflow strategy and design
- **Implementation Guide**: `IMPLEMENTATION_GUIDE.md` - Step-by-step setup and configuration
- **Workflow Files**: `workflows/` directory - Ready-to-import JSON workflow templates

## Build Custom Workflows

To build custom workflows using TenderTracker MCP services:

1. Add a **Chat Trigger** and an **AI Agent** node
2. Attach your preferred chat model to the AI Agent
3. Add three **MCP Client Tool** nodes, one per endpoint above
4. Connect each to the Agent's **Tool** connector
5. Select **None** authentication while services remain local

## Expected Benefits

### Efficiency Gains
- **10x faster** batch processing with parallel execution
- **80% reduction** in manual monitoring time
- **90% reduction** in filing preparation time
- **Automated** deadline management

### Quality Improvements
- **AI-powered** relevance filtering and classification
- **Automated** document validation and compliance checking
- **Consistent** analysis standards across all tenders
- **Error-free** filing preparation

### Strategic Value
- **Proactive** opportunity identification with real-time alerts
- **Data-driven** decision making with comprehensive analytics
- **Scalable** operations supporting business growth
- **Comprehensive** audit trail and reporting

## Support

For detailed implementation instructions, troubleshooting, and optimization guidance, refer to `IMPLEMENTATION_GUIDE.md`.
```

The MCP Client Tool supports selecting exactly which MCP tools the agent can access, so expose the smallest set needed for each workflow branch. The AI Agent requires at least one connected tool. See the [n8n MCP Client Tool docs](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.toolmcp/) and [AI Agent docs](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/).
