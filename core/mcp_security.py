"""MCP URL validation and SSRF protection."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from core.config import settings


class MCPValidationError(Exception):
    pass


def validate_mcp_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise MCPValidationError(f"Invalid MCP scheme: {parsed.scheme}")
    host = parsed.hostname
    if not host:
        raise MCPValidationError("MCP URL missing hostname")
    allowed = settings.allowed_mcp_hosts_list
    if host not in allowed:
        raise MCPValidationError(f"MCP host not allowlisted: {host}")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private and "localhost" not in allowed and host != "127.0.0.1":
            raise MCPValidationError("Private IP MCP targets denied")
    except ValueError:
        pass


def validate_mcp_response(payload: dict, max_size_bytes: int = 512_000) -> dict:
    import json

    encoded = json.dumps(payload)
    if len(encoded) > max_size_bytes:
        raise MCPValidationError("MCP response exceeds max payload size")
    if not isinstance(payload, dict):
        raise MCPValidationError("MCP response must be a dict")
    return payload
