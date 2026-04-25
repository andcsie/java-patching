"""MCP (Model Context Protocol) server for Java Patching tools.

Uses FastMCP for clean decorator-based tool definitions.
"""

from app.mcp.server import mcp

__all__ = ["mcp"]
