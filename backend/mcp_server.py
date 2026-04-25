#!/usr/bin/env python3
"""
MCP Server entry point for Java Patching tools.

This script starts the FastMCP server that exposes Java Patching
capabilities to MCP clients like Claude Code and Claude Desktop.

Usage:
    python mcp_server.py

    # Or with uvx (recommended)
    uvx fastmcp run backend/app/mcp/server.py:mcp

Configuration for Claude Code (~/.claude/settings.json or mcp-config.json):
    {
        "mcpServers": {
            "java-patching": {
                "command": "python",
                "args": ["/path/to/JavaPatching/backend/mcp_server.py"]
            }
        }
    }

Alternative using uvx:
    {
        "mcpServers": {
            "java-patching": {
                "command": "uvx",
                "args": ["fastmcp", "run", "backend/app/mcp/server.py:mcp"],
                "cwd": "/path/to/JavaPatching"
            }
        }
    }
"""

import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.mcp.server import mcp

if __name__ == "__main__":
    mcp.run()
