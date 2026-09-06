"""MyIIS MCP - Model Context Protocol server for BSUIR IIS API."""

from .server import app, mcp

__version__ = "0.1.0"
__all__ = ["app", "mcp", "__version__"]
