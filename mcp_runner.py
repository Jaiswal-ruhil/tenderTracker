# Model Context Protocol (MCP) Runner for TenderTracker
# Used as entry point for configuring MCP servers in Claude Desktop, Cursor, or other clients.

import os
import sys
import argparse
import subprocess

# Ensure we use the virtual environment's Python if available
venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
if os.path.exists(venv_python):
    norm_venv = os.path.normpath(os.path.abspath(venv_python))
    norm_sys = os.path.normpath(os.path.abspath(sys.executable))
    if norm_sys != norm_venv:
        # Re-execute using the virtual environment
        result = subprocess.run([venv_python] + sys.argv)
        sys.exit(result.returncode)

# Add src and src/core to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "core"))

SERVER_MODULES = {
    "legacy": "mcp_server",
    "catalog": "mcp_catalog_server",
    "analysis": "mcp_analysis_server",
    "filing": "mcp_filing_server",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run a TenderTracker MCP server")
    parser.add_argument("--server", choices=SERVER_MODULES, default="legacy")
    parser.add_argument("--transport", choices=("stdio", "sse", "streamable-http"), default="stdio")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    module = __import__(SERVER_MODULES[args.server], fromlist=["mcp"])
    module.mcp.run(transport=args.transport)
