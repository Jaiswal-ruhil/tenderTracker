# Model Context Protocol (MCP) Runner for TenderTracker
# Used as entry point for configuring MCP servers in Claude Desktop, Cursor, or other clients.

import os
import sys
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

# Run the server
from mcp_server import mcp

if __name__ == "__main__":
    mcp.run()
