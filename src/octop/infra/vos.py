"""Product-owned VOS skills and MCP assembly, enabled only inside a tenant jail."""

from __future__ import annotations

import os
import sys
from typing import Any


def add_vos_capabilities(
    skills: list[str], servers: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    """Attach the read-only skill bundle and the user's local capability sockets."""
    root = os.environ.get("VA_SKILLS_DIR")
    if not root:
        return skills, servers
    servers = dict(servers)
    servers["vos-apps"] = {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["/usr/local/lib/v-agent/vos/mcp_server.py"],
        "env": {"HOME": os.environ.get("HOME", "")},
    }
    return [*skills, root], servers
