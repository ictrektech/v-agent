"""VOS MCP tools. Unix socket ownership determines the calling account."""

from __future__ import annotations

import asyncio
import http.client
import json
import os
import socket
from pathlib import Path
from typing import Literal

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("v-Octop VOS apps")


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
        connection.request(
            method,
            path,
            body=json.dumps(body) if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024:
            raise ValueError("Response too large; use the app skill's download command")
        return {"status": response.status, "body": data.decode("utf-8", errors="replace")}
    finally:
        connection.close()


@mcp.tool()
async def vos_api(
    service: Literal["voffice", "album", "image-studio", "photocraft"],
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
    path: str,
    body: dict | None = None,
) -> dict:
    """Call a VOS app as the current user, without asking for credentials.

    voffice: GET /api/v1/me or /api/v1/files. album: GET /users/me or /albums.
    HybRAG knowledge retrieval is provided by its automatically connected native connector.
    image-studio: GET /api/v1/models, POST /api/v1/generate.
    photocraft: GET /volumes or /index. Use its dedicated MCP tools to edit.
    Each service proxy enforces its API allowlist and the upstream user's permissions.
    Use the corresponding installed skill for detailed commands and file transfers.
    """
    return await asyncio.to_thread(request, service, method, path, body)


@mcp.tool()
async def scheduler_catalog() -> dict:
    """Discover the current user's V-Scheduler models, categories and actual inference endpoints."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            os.environ["VA_SCHEDULER_URL"] + "/catalog",
            headers={"Authorization": "Bearer " + os.environ["VA_SCHEDULER_KEY"]},
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def scheduler_infer(
    path: str,
    body: dict,
    method: Literal["GET", "POST"] = "POST",
    file_path: str | None = None,
    output_file: str | None = None,
) -> dict:
    """Call a discovered V-Scheduler inference endpoint as the current VOS user.

    Supports embeddings, images/video generation, speech, ASR, ML predictions,
    rerank and System One decisions. Discover the model and endpoint first.
    file_path uploads a workspace file as multipart; body supplies other fields.
    output_file saves binary results inside the current workspace. Do not invent
    outputs from job acceptance: poll the returned task through its allowed endpoint.
    """
    if not path.startswith("/v1/") or ".." in path or path.startswith("//"):
        raise ValueError("Use a discovered /v1/ inference path")
    headers = {"Authorization": "Bearer " + os.environ["VA_SCHEDULER_KEY"]}
    async with httpx.AsyncClient(timeout=300) as client:
        kwargs = {}
        if file_path:
            source = Path(file_path).resolve()
            if not source.is_relative_to(Path.home().resolve()):
                raise ValueError("Upload only files inside your own home/workspace")
            kwargs = {
                "files": {"file": (source.name, source.read_bytes())},
                "data": {key: str(value) for key, value in body.items()},
            }
        elif method == "POST":
            kwargs = {"json": body}
        else:
            kwargs = {"params": body}
        response = await client.request(
            method, os.environ["VA_SCHEDULER_URL"] + path, headers=headers, **kwargs
        )
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            return {"status": response.status_code, "body": response.json()}
        response.raise_for_status()
        if not output_file:
            raise ValueError("Specify output_file for a binary inference result")
        target = Path(output_file).resolve()
        if not target.is_relative_to(Path.cwd().resolve()):
            raise ValueError("Save results inside the current workspace")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        return {
            "status": response.status_code,
            "file": str(target),
            "content_type": content_type,
            "bytes": len(response.content),
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")
