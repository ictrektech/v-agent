"""PhotoCraft MCP bridge over the current user's gateway-owned Unix socket."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.fastmcp import FastMCP

queue = None


def client_factory(headers=None, timeout=None, auth=None):
    return httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        auth=auth,
        transport=httpx.AsyncHTTPTransport(uds=str(Path.home() / ".vagent/photocraft.sock")),
    )


async def serve_calls():
    """One transport owner keeps native documents and sessions alive across calls."""
    while True:
        item = await queue.get()
        if item is None:
            return
        try:
            async with (
                streamablehttp_client(
                    "http://localhost/mcp", httpx_client_factory=client_factory
                ) as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                while True:
                    operation, arguments, future = item
                    try:
                        result = (
                            await session.list_tools()
                            if operation == "catalog"
                            else await session.call_tool(operation, arguments)
                        )
                        payload = result.model_dump(mode="json")
                        if operation == "catalog":
                            payload["tools"] = [
                                tool
                                for tool in payload["tools"]
                                if not tool["name"].startswith("ui_")
                                and tool["name"] != "control_call"
                            ]
                        if not future.done():
                            future.set_result(payload)
                    except Exception as error:
                        if not future.done():
                            future.set_exception(error)
                    item = await queue.get()
                    if item is None:
                        return
        except asyncio.CancelledError:
            raise
        except Exception:
            if item is None:
                return
            future = item[2]
            if not future.done():
                future.set_exception(
                    RuntimeError(
                        "PhotoCraft is unavailable; install its VOS MCP-enabled release and refresh v-agent."
                    )
                )


@asynccontextmanager
async def lifespan(_server):
    global queue
    queue = asyncio.Queue()
    task = asyncio.create_task(serve_calls())
    try:
        yield {}
    finally:
        await queue.put(None)
        try:
            await asyncio.wait_for(task, 10)
        except TimeoutError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


mcp = FastMCP("PhotoCraft", lifespan=lifespan)


@mcp.tool()
async def photocraft_catalog() -> dict:
    """List PhotoCraft's actual native MCP tools and their schemas before editing."""
    future = asyncio.get_running_loop().create_future()
    await queue.put(("catalog", {}, future))
    return await asyncio.wait_for(future, 45)


@mcp.tool()
async def photocraft_call(tool: str, arguments: dict) -> dict:
    """Call a tool discovered by photocraft_catalog as the current VOS user.

    Native tools include document creation/open, command inspection/batches,
    preview and export. Keep one document session across calls. Never guess schemas.
    """
    if tool.startswith("ui_") or tool == "control_call":
        raise ValueError("Desktop UI tools are unavailable in the VOS headless app")
    future = asyncio.get_running_loop().create_future()
    await queue.put((tool, arguments, future))
    return await asyncio.wait_for(future, 300)


if __name__ == "__main__":
    mcp.run(transport="stdio")
