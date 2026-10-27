"""Launch a single user's Octop inside the VOS gateway's OS jail."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import secrets
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

import uvicorn

from octop.api.app import build_app
from octop.infra.agents.manager import AgentCreateSpec
from octop.infra.auth.tokens import sign_token
from octop.infra.server import OctopServer

log = logging.getLogger("v-agent")


def catalog():
    request = Request(os.environ["VA_SCHEDULER_URL"] + "/v1/models", headers={
        "Authorization": "Bearer " + os.environ["VA_SCHEDULER_KEY"],
    })
    with urlopen(request, timeout=20) as response:
        return json.load(response)["data"]


async def synchronize(server):
    """Refresh only the calling VOS user's models; leave private providers intact."""
    models = await asyncio.to_thread(catalog)
    repo = server.services.provider_repo
    groups = {}
    for row in models:
        # Text-only completion endpoints cannot drive an agent tool loop.
        if row["api"] == "text-completions":
            continue
        groups.setdefault(row["api"], []).append({
            "id": row["id"], "name": row["name"], "input": row.get("input", ["text"]),
            "api_mode": "responses" if row["api"] == "openai-responses" else "chat_completions",
        })
    for api in ["openai-completions", "openai-responses", "anthropic-messages"]:
        name = "vos-" + api
        values = groups.get(api, [])
        current = repo.get_by_name(name)
        fields = dict(kind="anthropic" if api == "anthropic-messages" else "openai",
                      base_url=os.environ["VA_SCHEDULER_URL"] + "/v1",
                      api_key=os.environ["VA_SCHEDULER_KEY"],
                      models_json=json.dumps(values, ensure_ascii=False))
        if current:
            if current.models_json == fields["models_json"] and current.api_key == fields["api_key"]:
                continue
            repo.update(current.id, **fields, enabled=bool(values))
        elif values:
            repo.create(name=name, **fields)
        else:
            continue
        await server.app_runtime.agent_registry.on_provider_changed()
    registry = server.app_runtime.agent_registry
    user = server.user_manager.get("vos")
    if groups and not registry.list_agents(user.id):
        user = server.user_manager.get("vos")
        await registry.create(AgentCreateSpec(
            name="v-agent", user_id=user.id,
            system_prompt="You are v-agent, the user's VOS assistant. Use the installed VOS skills and MCP tools for platform apps; their credentials are managed for this user. Save deliverables inside your workspace.",
        ))


async def main():
    root = Path(os.environ["OCTOP_HOME"])
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not (root / "octop.db").exists():
        env = dict(os.environ, OCTOP_ADMIN_USERNAME="vos", OCTOP_ADMIN_PASSWORD="Va9" + secrets.token_urlsafe(40))
        subprocess.run(["octop", "init", "--yes", "--admin-display-name", os.environ["VA_DISPLAY_NAME"]],
                       env=env, check=True, stdout=subprocess.DEVNULL)
    config_file = root / "config.json"
    config = json.loads(config_file.read_text()) if config_file.exists() else {}
    config["enable_api_docs"] = True
    config_file.write_text(json.dumps(config))
    server = OctopServer()
    await server.start()
    await server.user_manager.set_display_name("vos", os.environ["VA_DISPLAY_NAME"])
    try:
        await synchronize(server)
    except Exception:
        log.exception("V-Scheduler catalog unavailable; retrying in background")
    token_file = Path.home() / ".vagent" / "runtime-token"

    def renew():
        user = server.user_manager.get("vos")
        token = sign_token(server.services.secret_repo.get("jwt"), sub=user.id,
                           uname=user.username, role=user.role, ttl_seconds=86400 * 30)
        temp = token_file.with_suffix(".tmp")
        temp.write_text(token)
        temp.chmod(0o600)
        temp.replace(token_file)

    renew()

    async def refresh():
        while True:
            await asyncio.sleep(60)
            try:
                await synchronize(server)
                renew()
            except Exception:
                log.exception("V-Scheduler refresh failed")

    task = asyncio.create_task(refresh())
    try:
        app = build_app(server)
        app.title = "v-agent API"
        await uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=int(os.environ["VA_PORT"]),
                                           log_level="warning")).serve()
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
