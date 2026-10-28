"""Product-owned VOS skills and MCP assembly, enabled only inside a tenant jail."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


def vos_mcp_server_names() -> list[str]:
    """Account-scoped product capabilities, independent of optional connectors."""
    return ["vos-apps", "photocraft"] if os.environ.get("VA_SKILLS_DIR") else []


async def synchronize_hybrag_connector(services: Any, user_id: int) -> None:
    """Discover the current VOS user's HybRAG area without storing upstream keys.

    Absence is normal. The runtime repeats this probe so a later installation
    connects automatically; a disconnected service never produces a UI error.
    """
    if not os.environ.get("VA_SKILLS_DIR"):
        return
    repo = services.repos.connector_repo
    managed = next(
        (
            row
            for row in repo.list_by_user(user_id)
            if row.kind == "weknora" and json.loads(row.config_json or "{}").get("vos_managed")
        ),
        None,
    )
    available = False
    try:
        transport = httpx.AsyncHTTPTransport(uds=str(Path.home() / ".vagent" / "weknora.sock"))
        async with httpx.AsyncClient(transport=transport, timeout=4) as client:
            response = await client.get("http://localhost/api/v1/knowledge-bases")
            payload = response.json()
            available = (
                response.status_code == 200
                and isinstance(payload, dict)
                and payload.get("success") is not False
            )
    except (httpx.HTTPError, ValueError, OSError):
        pass
    if not available:
        if managed is not None and managed.status == "active":
            repo.update_status(managed.instance_id, "inactive")
        return
    from octop.infra.connectors.builder import mcp_server_name
    from octop.infra.connectors.service import ConnectorService
    from octop.infra.utils.ulid import new_ulid

    if managed is None:
        instance_id = new_ulid()
        repo.create(
            instance_id=instance_id,
            user_id=user_id,
            kind="weknora",
            display_name="HybRAG",
            mcp_server_name=mcp_server_name("weknora", instance_id),
            config_json=json.dumps({"vos_managed": True, "default_open": True}),
        )
    else:
        instance_id = managed.instance_id
        if managed.status == "inactive":
            repo.update_status(instance_id, "active")
    service = ConnectorService(
        repo=repo,
        secret_repo=services.secret_repo,
        settings_repo=services.settings_repo,
        config=services.config,
    )
    credentials = {"base_url": "http://127.0.0.1", "vos_managed": True}
    existing = service.decrypt(instance_id)
    if any(existing.get(key) != value for key, value in credentials.items()):
        service.encrypt_and_store(instance_id=instance_id, payload=credentials)


def add_vos_capabilities(
    skills: list[str], servers: dict[str, Any], *, agent_id: str = "default"
) -> tuple[list[str], dict[str, Any]]:
    """Attach the read-only skill bundle and the user's local capability sockets."""
    root = os.environ.get("VA_SKILLS_DIR")
    if not root:
        return skills, servers
    servers = dict(servers)
    servers["vos-apps"] = {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["/usr/local/lib/v-octop/vos/mcp_server.py"],
        "env": {
            key: os.environ[key]
            for key in ("HOME", "VA_SCHEDULER_URL", "VA_SCHEDULER_KEY")
            if key in os.environ
        },
    }
    servers["photocraft"] = {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["/usr/local/lib/v-octop/vos/photocraft_mcp.py"],
        "env": {
            "HOME": os.environ.get("HOME", ""),
            "VA_PHOTOCRAFT_SESSION_SCOPE": agent_id,
        },
    }
    return [*skills, root], servers
