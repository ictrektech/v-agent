"""VOS MCP tools. Unix socket ownership determines the calling account."""
from __future__ import annotations

import asyncio
import http.client
import json
import socket
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("v-agent VOS apps")


class LocalConnection(http.client.HTTPConnection):
    def __init__(self, service: str):
        super().__init__("localhost", timeout=120)
        self.socket_path = str(Path.home() / ".vagent" / (service + ".sock"))

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def request(service: str, method: str, path: str, body: dict | None):
    if not path.startswith("/") or path.startswith("//") or ".." in path:
        raise ValueError("Use a service-relative API path")
    connection = LocalConnection(service)
    try:
        connection.request(method, path, body=json.dumps(body) if body is not None else None,
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024:
            raise ValueError("Response too large; use the app skill's download command")
        return {"status": response.status, "body": data.decode("utf-8", errors="replace")}
    finally:
        connection.close()


@mcp.tool()
async def vos_api(
    service: Literal["voffice", "album", "weknora", "image-studio"],
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
    path: str,
    body: dict | None = None,
) -> dict:
    """Call a VOS app as the current user, without asking for credentials.

    voffice: GET /api/v1/me or /api/v1/files. album: GET /users/me or /albums.
    weknora: GET /api/v1/knowledge-bases, POST /api/v1/knowledge-search.
    image-studio: GET /api/v1/models, POST /api/v1/generate.
    Each service proxy enforces its API allowlist and the upstream user's permissions.
    Use the corresponding installed skill for detailed commands and file transfers.
    """
    return await asyncio.to_thread(request, service, method, path, body)


if __name__ == "__main__":
    mcp.run(transport="stdio")
