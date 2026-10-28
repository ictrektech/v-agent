"""PhotoCraft tools using a resumable native session on the user's private socket.

Harness MCP adapters launch a new stdio process for each invocation. Keep the native
session id in the user's private home, not in that short-lived process. A file lock
serializes calls; PhotoCraft still authenticates every request through the gateway.
"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import os
import secrets
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PhotoCraft")


def _client():
    return httpx.Client(
        transport=httpx.HTTPTransport(uds=str(Path.home() / ".vagent/photocraft.sock")),
        base_url="http://localhost",
        timeout=300,
    )


def _send(client, method, params, state=None):
    headers = {"accept": "application/json, text/event-stream"}
    if state:
        headers.update({"mcp-session-id": state["id"], "mcp-protocol-version": state["protocol"]})
    notification = method.startswith("notifications/")
    request_id = secrets.token_hex(8)
    body = {"jsonrpc": "2.0", "method": method, "params": params}
    if not notification:
        body["id"] = request_id
    with client.stream("POST", "/mcp", json=body, headers=headers) as response:
        response.raise_for_status()
        response_headers = dict(response.headers)
        if notification:
            response.read()
            return {}, response_headers
        if "text/event-stream" in response.headers.get("content-type", ""):
            data = []
            for line in response.iter_lines():
                if line.startswith("data:"):
                    data.append(line[5:].lstrip())
                elif not line:
                    payload = "\n".join(data)
                    data = []
                    if not payload.strip():
                        continue
                    envelope = json.loads(payload)
                    if envelope.get("id") == request_id:
                        break
            else:
                raise RuntimeError("PhotoCraft returned no tool response")
        else:
            envelope = json.loads(response.read())
    if "error" in envelope:
        raise RuntimeError(str(envelope["error"].get("message", "PhotoCraft request failed")))
    return envelope["result"], response_headers


def native_request(method, params):
    scope = os.environ.get("VA_PHOTOCRAFT_SESSION_SCOPE", "default")
    directory = Path.home() / ".vagent/photocraft-sessions"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = hashlib.sha256(scope.encode()).hexdigest()
    state_file = directory / (key + ".json")
    descriptor = os.open(directory / (key + ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "w"), _client() as client:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            state = json.loads(state_file.read_text()) if state_file.exists() else None
            if state:
                try:
                    return _send(client, method, params, state)[0]
                except httpx.HTTPStatusError as error:
                    if error.response.status_code != 404:
                        raise
            # Negotiate a stateful MCP version; later protocol versions may be stateless.
            result, headers = _send(
                client,
                "initialize",
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "v-Octop", "version": "1"},
                },
            )
            session_id = headers.get("mcp-session-id")
            if not session_id:
                raise RuntimeError("PhotoCraft did not establish a document session")
            state = {"id": session_id, "protocol": result["protocolVersion"]}
            state_fd = os.open(state_file, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
            with os.fdopen(state_fd, "w") as file:
                json.dump(state, file)
            _send(client, "notifications/initialized", {}, state)
            return _send(client, method, params, state)[0]
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)


@mcp.tool()
async def photocraft_catalog() -> dict:
    """List PhotoCraft's native tools and schemas before editing."""
    payload = await asyncio.to_thread(native_request, "tools/list", {})
    payload["tools"] = [
        tool
        for tool in payload["tools"]
        if not tool["name"].startswith("ui_") and tool["name"] != "control_call"
    ]
    return payload


@mcp.tool()
async def photocraft_call(tool: str, arguments: dict) -> dict:
    """Call a discovered native tool. The active document survives consecutive calls."""
    if tool.startswith("ui_") or tool == "control_call":
        raise ValueError("Desktop UI tools are unavailable in the VOS headless app")
    return await asyncio.to_thread(
        native_request, "tools/call", {"name": tool, "arguments": arguments}
    )


def _volume(client):
    response = client.get("/volumes")
    response.raise_for_status()
    volumes = response.json()["data"]["data"]
    if not volumes:
        raise ValueError("PhotoCraft has no directory authorized for the current VOS user")
    return next(
        (
            v
            for v in volumes
            if v["name"].split("/")[-3:-2] == ["users"] and v["name"].split("/")[-1:] == ["data"]
        ),
        volumes[0],
    )


def _checked(result):
    if result.get("isError"):
        raise ValueError("PhotoCraft operation failed: " + json.dumps(result.get("content", [])))
    return result


def _import(file_path):
    source = Path(file_path).expanduser().resolve(strict=True)
    name = "v-octop-" + secrets.token_hex(8) + "-" + source.name
    with _client() as client:
        volume = _volume(client)
        with source.open("rb") as file:
            response = client.post(
                "/upload",
                params={
                    "adapter": volume["adapter"],
                    "path": volume["adapter"] + "://",
                    "name": name,
                },
                content=file,
            )
        response.raise_for_status()
        if response.json().get("code") != 0:
            raise ValueError("PhotoCraft rejected the image import")
    document = _checked(
        native_request("tools/call", {"name": "doc_open", "arguments": {"path": name}})
    )
    return {"path": name, "document": document}


@mcp.tool()
async def photocraft_import(file_path: str) -> dict:
    """Upload an existing user-selected workspace image to PhotoCraft and open it.

    Returns the authorized native path and document. Use photocraft_call for edits,
    then photocraft_export to bring the edited result back to the workspace.
    """
    return await asyncio.to_thread(_import, file_path)


def _export(output_file):
    target = Path(output_file).expanduser().resolve()
    name = "v-octop-" + secrets.token_hex(8) + "-" + target.name
    saved = _checked(
        native_request("tools/call", {"name": "doc_save", "arguments": {"path": name}})
    )
    with _client() as client:
        volume = _volume(client)
        response = client.get(
            "/download",
            params={
                "adapter": volume["adapter"],
                "path": volume["adapter"] + "://" + name,
            },
        )
        response.raise_for_status()
        target.write_bytes(response.content)
    return {
        "output_file": str(target),
        "bytes": target.stat().st_size,
        "document": saved,
    }


@mcp.tool()
async def photocraft_export(output_file: str) -> dict:
    """Export the active PhotoCraft document to a user-chosen workspace file.

    The filename extension selects PNG, PSD or another supported native format.
    The parent directory must already exist. Existing output files are replaced.
    """
    return await asyncio.to_thread(_export, output_file)


if __name__ == "__main__":
    mcp.run(transport="stdio")
