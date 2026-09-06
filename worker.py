"""Cloudflare Workers and Universal ASGI entrypoint for MyIIS MCP."""

from myiis_mcp.server import app

try:
    from workers import asgi  # Available in Cloudflare Python Workers runtime
    Default = asgi.entrypoint(app)
except ImportError:
    # Standard ASGI runtime (uvicorn, gunicorn, etc.)
    Default = app
