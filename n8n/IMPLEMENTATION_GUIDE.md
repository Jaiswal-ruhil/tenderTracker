# n8n Workflow Implementation Guide

## Prerequisites

### Required Components
- **TenderTracker Application**: Running with MCP servers enabled
- **n8n Instance**: Docker or local installation
- **MCP Servers**: Three MCP servers running on SSE endpoints
- **Notification Services**: Slack, Email (optional but recommended)

### MCP Server Setup
Before implementing n8n workflows, ensure all three MCP servers are running:

```powershell
# Terminal 1 - Catalog MCP
python mcp_runner.py --server catalog --transport sse

# Terminal 2 - Analysis MCP  
python mcp_runner.py --server analysis --transport sse

# Terminal 3 - Filing MCP
python mcp_runner.py --server filing --transport sse
```

Verify endpoints are accessible:
- Catalog: `http://127.0.0.1:8101/sse`
- Analysis: `http://127.0.0.1:8102/sse`
- Filing: `http://127.0.0.1:8103/sse`

## n8n Installation

### Option 1: Docker Installation (Recommended)
```bash
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

### Option 2: Local Installation
```bash
npm install n8n -g
n8n start
```

Access n8n at `http://localhost:5678`

## Workflow Import Process

### Step 1: Access n8n Interface
1. Open browser to `http://localhost:5678`
2. Login or create account
3. Navigate to "Workflows" section

### Step 2: Import Workflows
For each workflow JSON file:

1. Click "Import from File" or "Import from URL"
2. Select the JSON file:
   - `automated_tender_monitoring.json`
   - `batch_processing.json` 
   - `automated_filing.json`
3. Review the imported workflow structure
4. Save the workflow

### Step 3: Configure MCP Connections

Each workflow requires MCP Client Tool nodes to be configured:

#### Configure Catalog MCP Client
1. Find nodes with `mcpClient` pointing to port 8101
2. Configure MCP Client settings:
   - **Mode**: SSE
   - **URL**: `http://127.0.0.1:8101/sse` (or `http://host.docker.internal:8101/sse` for Docker)
   - **Authentication**: None (for local development)

#### Configure Analysis MCP Client
1. Find nodes with `mcpClient` pointing to port 8102
2. Configure MCP Client settings:
   - **Mode**: SSE
   - **URL**: `http://127.0.0.1:8102/sse` (or `http://host.docker.internal:8102/sse` for Docker)
   - **Authentication**: None

#### Configure Filing MCP Client
1. Find nodes with `mcpClient` pointing to port 8103
2. Configure MCP Client settings:
   - **Mode**: SSE
   - **URL**: `http://127.0.0.1:8103/sse` (or `http://host.docker.internal:8103/sse` for Docker)
   - **Authentication**: None

### Step 4: Configure Notification Services

#### Slack Integration
1. Create a Slack App and Bot Token
2. In n8n, add Slack credentials:
   - Go to Credentials → Add Credential
   - Select "Slack API"
   - Enter Bot Token and Workspace ID
3. Update Slack nodes in workflows:
   - Set channel names (e.g., `tendertracker-alerts`, `tendertracker-filing`)
   - Test connection

#### Email Integration
1. Configure SMTP settings in n8n:
   - Go to Credentials → Add Credential
   - Select "SMTP"
   - Enter SMTP server details
2. Update Email nodes:
   - Set recipient email addresses
   - Configure sender details
   - Test email sending

## Workflow-Specific Configuration

### 1. Automated Tender Monitoring

#### Configuration Steps
1. **Schedule Trigger**: 
   - Set to run every 2 hours during business hours (8 AM - 8 PM)
   - Adjust timezone as needed

2. **HTTP Request Node**:
   - Configure GeM portal scraping endpoint
   - Add authentication if required
   - Set timeout values

3. **Filter Thresholds**:
   - Adjust confidence score threshold (default: 0.7)
   - Modify company criteria matching logic

4. **Notification Channels**:
   - Configure Slack channel for alerts
   - Set email recipients for high-priority tenders

#### Testing
1. Manually trigger the workflow
2. Verify MCP connections work
3. Check that tenders are being classified
4. Confirm notifications are sent
4. Validate search index rebuild

### 2. Batch Processing Workflow

#### Configuration Steps
1. **File Upload Node**:
   - Configure allowed file types (CSV, TXT, PDF)
   - Set file size limits
   - Configure storage location

2. **Batch Size**:
   - Adjust batch size (default: 10 tenders)
   - Balance between speed and resource usage

3. **Excel Export**:
   - Configure output format
   - Set file naming convention
   - Configure storage location

4. **Statistics Calculation**:
   - Customize metrics to track
   - Adjust success rate calculations

#### Testing
1. Upload sample tender data file
2. Verify batch processing works
3. Check AI analysis results
4. Validate Excel export
5. Confirm completion notifications

### 3. Automated Filing Workflow

#### Configuration Steps
1. **Input Parameters**:
   - Configure required fields (bid_no, firm_name)
   - Add validation for input data
   - Set default values if needed

2. **Document Validation**:
   - Configure validation rules
   - Set tolerance levels for document matching
   - Customize GEM requirements mapping

3. **Folder Structure**:
   - Configure filing folder naming convention
   - Set base directory for filing folders
   - Configure backup locations

4. **Report Generation**:
   - Customize report template
   - Configure report storage
   - Set email distribution list

#### Testing
1. Test with valid tender number
2. Test with invalid tender number
3. Verify document validation works
4. Check filing folder creation
5. Validate report generation
6. Test notification scenarios

## Docker-Specific Configuration

If running n8n in Docker, use `host.docker.internal` instead of `127.0.0.1`:

```json
{
  "mcpClient": {
    "__rl": true,
    "mode": "sse",
    "url": "http://host.docker.internal:8101/sse",
    "authentication": "none"
  }
}
```

## Error Handling and Monitoring

### Common Issues and Solutions

#### MCP Connection Failures
**Problem**: MCP Client nodes fail to connect
**Solution**: 
- Verify MCP servers are running
- Check URL configuration (127.0.0.1 vs host.docker.internal)
- Ensure no firewall blocking connections
- Check MCP server logs

#### Authentication Errors
**Problem**: Authentication fails for MCP or notification services
**Solution**:
- Verify credentials are correctly configured
- Check token validity
- Ensure proper permissions are granted

#### Timeout Issues
**Problem**: Workflows timeout during AI processing
**Solution**:
- Increase timeout values in MCP Client nodes
- Reduce batch sizes
- Optimize AI model performance
- Check system resources

#### Data Validation Errors
**Problem**: Tender data fails validation
**Solution**:
- Check input data format
- Verify required fields are present
- Review validation rules
- Check MCP tool error messages

### Monitoring Setup

#### Workflow Execution Logs
1. Enable workflow execution logs in n8n settings
2. Set up log retention policies
3. Configure error alerting

#### Performance Monitoring
1. Monitor workflow execution times
2. Track MCP server response times
3. Monitor system resource usage
4. Set up performance alerts

#### Success Metrics
Track key metrics:
- Workflow success rate
- Average processing time
- Number of tenders processed
- Notification delivery rate
- Error frequency

## Security Considerations

### Credential Management
1. Use n8n's credential system for sensitive data
2. Never hardcode API keys or passwords
3. Rotate credentials regularly
4. Use environment variables for configuration

### Data Protection
1. Encrypt sensitive tender data
2. Implement access controls
3. Regular backup of workflow configurations
4. Audit trail for workflow executions

### Network Security
1. Use HTTPS for external connections
2. Implement rate limiting
3. Configure firewall rules
4. Monitor for suspicious activity

## Maintenance and Updates

### Regular Maintenance Tasks
1. **Weekly**: Review workflow execution logs
2. **Monthly**: Update MCP server configurations
3. **Quarterly**: Review and optimize workflows
4. **As needed**: Update notification configurations

### Workflow Updates
When updating workflows:
1. Export current workflow as backup
2. Test changes in development environment
3. Document changes and reasons
4. Update this implementation guide

### MCP Server Updates
When MCP servers are updated:
1. Test backward compatibility
2. Update workflow configurations if needed
3. Update MCP Client tool configurations
4. Test all affected workflows

## Troubleshooting Guide

### Workflow Not Triggering
**Symptoms**: Schedule trigger not executing
**Solutions**:
- Check n8n is running
- Verify schedule configuration
- Check timezone settings
- Review n8n logs

### MCP Tool Not Responding
**Symptoms**: MCP Client nodes timeout
**Solutions**:
- Verify MCP server is running
- Check network connectivity
- Review MCP server logs
- Increase timeout values

### Notifications Not Sending
**Symptoms**: Slack/Email notifications not received
**Solutions**:
- Verify credential configuration
- Check notification service status
- Test notification nodes individually
- Review message formatting

### Data Not Persisting
**Symptoms**: Tender data not saved to database
**Solutions**:
- Verify database connection
- Check MCP Catalog server logs
- Review data format
- Test MCP tool directly

## Performance Optimization

### Batch Processing Optimization
1. **Optimal Batch Size**: Test different batch sizes (5-20 tenders)
2. **Parallel Processing**: Enable parallel execution where possible
3. **Resource Management**: Monitor CPU and memory usage
4. **Caching**: Implement caching for repeated operations

### MCP Server Optimization
1. **Connection Pooling**: Reuse MCP connections
2. **Async Processing**: Use async operations where possible
3. **Load Balancing**: Distribute load across multiple instances
4. **Response Caching**: Cache frequently accessed data

### Workflow Optimization
1. **Node Optimization**: Remove unnecessary nodes
2. **Data Flow**: Minimize data transformations
3. **Error Handling**: Implement efficient error handling
4. **Logging**: Optimize logging verbosity

## Scaling Considerations

### Horizontal Scaling
1. **Multiple n8n Instances**: Run multiple n8n instances with load balancer
2. **MCP Server Clustering**: Deploy multiple MCP server instances
3. **Database Scaling**: Use database clustering for high availability
4. **Queue Management**: Implement message queues for workflow execution

### Vertical Scaling
1. **Resource Allocation**: Increase CPU and memory for n8n
2. **Database Performance**: Optimize database queries and indexing
3. **AI Model Optimization**: Use optimized AI models
4. **Network Bandwidth**: Ensure sufficient network capacity

## Support and Resources

### Documentation
- TenderTracker Documentation: `README.md`
- MCP Setup Guide: `MCP_SETUP.md`
- n8n Documentation: https://docs.n8n.io

### Community Resources
- n8n Community Forum: https://community.n8n.io
- TenderTracker Support: Internal support channels

### Getting Help
1. Check this implementation guide
2. Review workflow execution logs
3. Consult MCP server logs
4. Reach out to support team

## Next Steps

After implementing these workflows:

1. **Test Thoroughly**: Test each workflow with real data
2. **Monitor Performance**: Establish baseline performance metrics
3. **Gather Feedback**: Collect user feedback on workflow effectiveness
4. **Iterate**: Continuously improve workflows based on feedback
5. **Expand**: Consider implementing Phase 2 workflows from the plan

## Appendix: Quick Reference

### MCP Endpoints
- Catalog: `http://127.0.0.1:8101/sse`
- Analysis: `http://127.0.0.1:8102/sse`
- Filing: `http://127.0.0.1:8103/sse`

### Key MCP Tools
- **Catalog**: `get_bid`, `search_bids`, `add_tender_record`, `rebuild_search_index`
- **Analysis**: `extract_bid_blocks`, `classify_bid`, `generate_quote_requirements`, `match_company_products`
- **Filing**: `prepare_filing`, `validate_document_integrity`, `get_gem_requirements_mapping`

### Workflow Files
- `automated_tender_monitoring.json`
- `batch_processing.json`
- `automated_filing.json`

### Configuration Files
- `WORKFLOW_PLAN.md` - Overall workflow strategy
- `IMPLEMENTATION_GUIDE.md` - This file
- `README.md` - n8n integration overview
