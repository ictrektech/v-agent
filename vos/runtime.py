"""Launch a single user's Octop inside the VOS gateway's OS jail."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import secrets
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import uvicorn

from octop.api.app import build_app
from octop.infra.agents.manager import AgentCreateSpec
from octop.infra.auth.tokens import sign_token
from octop.infra.server import OctopServer
from octop.infra.vos import synchronize_hybrag_connector

log = logging.getLogger("v-Octop")
_decision_synced = False


def catalog():
    request = Request(
        os.environ["VA_SCHEDULER_URL"] + "/catalog",
        headers={
            "Authorization": "Bearer " + os.environ["VA_SCHEDULER_KEY"],
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)["models"]


def default_voice(model):
    request = Request(
        os.environ["VA_SCHEDULER_URL"] + "/v1/audio/voices?" + urlencode({"model": model}),
        headers={"Authorization": "Bearer " + os.environ["VA_SCHEDULER_KEY"]},
    )
    try:
        with urlopen(request, timeout=15) as response:
            value = json.load(response)
        voice = value.get("default_voice")
        if isinstance(voice, str) and voice:
            return voice
    except Exception:
        log.warning("V-Scheduler voice discovery unavailable")
    return None


async def synchronize(server):
    """Refresh only the calling VOS user's models; leave private providers intact."""
    models = await asyncio.to_thread(catalog)
    repo = server.services.provider_repo
    groups = {}
    embedding = []
    voices = []
    for row in models:
        if "embedding" in row.get("categories", []):
            embedding.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "embedding": True,
                    "task": "embedding",
                    "input": ["text"],
                }
            )
        if "voice" in row.get("categories", []):
            voices.append(row)
        if "chat" not in row.get("categories", ["chat"]):
            continue
        # Text-only completion endpoints cannot drive an agent tool loop.
        if row["api"] == "text-completions":
            continue
        groups.setdefault(row["api"], []).append(
            {
                "id": row["id"],
                "name": row["name"],
                "input": row.get("input", ["text"]),
                "api_mode": "responses" if row["api"] == "openai-responses" else "chat_completions",
            }
        )
    for api in ["openai-completions", "openai-responses", "anthropic-messages"]:
        name = "vos-" + api
        values = groups.get(api, [])
        current = repo.get_by_name(name)
        fields = {
            "kind": "anthropic" if api == "anthropic-messages" else "openai",
            "base_url": os.environ["VA_SCHEDULER_URL"] + "/v1",
            "api_key": os.environ["VA_SCHEDULER_KEY"],
            "models_json": json.dumps(values, ensure_ascii=False),
        }
        if current:
            if (
                current.models_json == fields["models_json"]
                and current.api_key == fields["api_key"]
            ):
                continue
            repo.update(current.id, **fields, enabled=bool(values))
        elif values:
            repo.create(name=name, **fields)
        else:
            continue
        await server.app_runtime.agent_registry.on_provider_changed()
    current = repo.get_by_name("vos-embeddings")
    fields = {
        "kind": "openai",
        "base_url": os.environ["VA_SCHEDULER_URL"] + "/v1",
        "api_key": os.environ["VA_SCHEDULER_KEY"],
        "extra_json": json.dumps({"purpose": "embedding"}),
        "models_json": json.dumps(embedding),
    }
    if current:
        repo.update(current.id, **fields, enabled=bool(embedding))
    elif embedding:
        repo.create(name="vos-embeddings", **fields)
    voice_repo = server.services.voice_provider_repo
    seen = set()
    for row in voices:
        for endpoint, capability in [("audio/transcriptions", "stt"), ("audio/speech", "tts")]:
            if endpoint not in row["endpoints"]:
                continue
            name = "vos-" + capability + "-" + row["id"]
            seen.add(name)
            current = voice_repo.get_by_name(name)
            extra = {"model": row["id"]}
            if capability == "tts":
                voice = await asyncio.to_thread(default_voice, row["id"])
                if voice:
                    extra["voice_id"] = voice
            fields = {
                "kind": "openai",
                "capability": capability,
                "base_url": os.environ["VA_SCHEDULER_URL"] + "/v1",
                "api_key": os.environ["VA_SCHEDULER_KEY"],
                "extra_json": json.dumps(extra),
            }
            if current:
                voice_repo.update(current.id, **fields, enabled=True)
            else:
                voice_repo.create(name=name, **fields)
    for row in voice_repo.list_all():
        if row.name.startswith(("vos-stt-", "vos-tts-")) and row.name not in seen:
            voice_repo.update(row.id, enabled=False)
    registry = server.app_runtime.agent_registry
    global _decision_synced
    decisions = [row for row in models if "systemone" in row.get("endpoints", [])]
    endpoint = os.environ["VA_SCHEDULER_URL"] + "/v1/systemone"
    view = registry.decision.load()
    if decisions and not _decision_synced:
        saved = next((item for item in view.services if item.provider == "scheduler"), None)
        legacy_managed = view.provider == "jev" and view.endpoint == endpoint
        selected_model = saved.model if saved else (view.model if legacy_managed else "")
        model_ids = [row["id"] for row in decisions]
        updates: list[dict[str, object]] = [
            {
                "provider": "scheduler",
                "endpoint": endpoint,
                "model": selected_model if selected_model in model_ids else model_ids[0],
                "api_key": os.environ["VA_SCHEDULER_KEY"],
            }
        ]
        if legacy_managed:
            updates.append({"provider": "jev", "endpoint": "", "model": "", "api_key": ""})
        await registry.save_decision(
            enabled=view.enabled,
            provider="scheduler" if legacy_managed else view.provider,
            endpoint=view.endpoint,
            model=view.model,
            skills=view.skills,
            tools=view.tools,
            team=view.team,
            threshold=view.threshold,
            tool_min_count=view.tool_min_count,
            services=updates,
        )
        _decision_synced = True
    user = server.user_manager.get(os.environ.get("VA_USERNAME", "vos"))
    if not server.services.settings_repo.get("vos_octop_brand_migrated"):
        for row in registry.list_agents(user.id):
            updates = {}
            if row.name == "v-agent":
                updates["name"] = "v-Octop"
            if row.system_prompt and "v-agent" in row.system_prompt:
                updates["system_prompt"] = row.system_prompt.replace("v-agent", "v-Octop")
            if updates:
                await registry.update(row.agent_id, **updates)
        server.services.settings_repo.set("vos_octop_brand_migrated", "true")
    if groups and not registry.list_agents(user.id):
        user = server.user_manager.get(os.environ.get("VA_USERNAME", "vos"))
        await registry.create(
            AgentCreateSpec(
                name="v-Octop",
                user_id=user.id,
                system_prompt="You are v-Octop, the user's VOS assistant. Use the installed VOS skills and MCP tools for platform apps; their credentials are managed for this user. Save deliverables inside your workspace.",
            )
        )


async def main():
    root = Path(os.environ["OCTOP_HOME"])
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not (root / "octop.db").exists():
        env = dict(
            os.environ,
            OCTOP_ADMIN_USERNAME=os.environ.get("VA_USERNAME", "vos"),
            OCTOP_ADMIN_PASSWORD="Va9" + secrets.token_urlsafe(40),
        )
        subprocess.run(
            ["octop", "init", "--yes", "--admin-display-name", os.environ["VA_DISPLAY_NAME"]],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    config_file = root / "config.json"
    config = json.loads(config_file.read_text()) if config_file.exists() else {}
    config["enable_api_docs"] = True
    config_file.write_text(json.dumps(config))
    server = OctopServer()
    await server.start()
    username = os.environ.get("VA_USERNAME", "vos")
    subject = os.environ.get("VA_SUBJECT", "")
    bound = server.services.settings_repo.get("vos_subject")
    if bound and bound != subject:
        raise RuntimeError("VOS identity does not match this workspace")
    legacy = server.services.user_repo.get_by_username("vos")
    if legacy and username != "vos":
        with server.services.db.transaction() as conn:
            conn.execute(
                "UPDATE users SET username = ?, password_hash = NULL WHERE id = ?",
                (username, legacy.id),
            )
    with server.services.db.transaction() as conn:
        conn.execute("UPDATE users SET password_hash = NULL WHERE username = ?", (username,))
    await server.user_manager.shutdown_all()
    await server.user_manager.boot()
    server.services.settings_repo.set("vos_subject", subject)
    await server.user_manager.set_display_name(username, os.environ["VA_DISPLAY_NAME"])
    await synchronize_hybrag_connector(server.services, server.user_manager.get(username).id)
    try:
        await synchronize(server)
    except Exception:
        log.exception("V-Scheduler catalog unavailable; retrying in background")
    token_file = Path.home() / ".vagent" / "runtime-token"

    def renew():
        user = server.user_manager.get(os.environ.get("VA_USERNAME", "vos"))
        token = sign_token(
            server.services.secret_repo.get("jwt"),
            sub=user.id,
            uname=user.username,
            role=user.role,
            ttl_seconds=86400 * 30,
        )
        temp = token_file.with_suffix(".tmp")
        temp.write_text(token)
        temp.chmod(0o600)
        temp.replace(token_file)

    renew()

    async def refresh():
        connector_refreshed = time.monotonic()
        while True:
            await asyncio.sleep(10)
            if time.monotonic() - connector_refreshed >= 60:
                await synchronize_hybrag_connector(
                    server.services, server.user_manager.get(username).id
                )
                connector_refreshed = time.monotonic()
            try:
                await synchronize(server)
                renew()
            except Exception:
                log.exception("V-Scheduler refresh failed")

    pgv_file = Path.home() / ".vagent" / "pgv.json"
    if pgv_file.exists():
        value = json.loads(pgv_file.read_text())
        backends = server.services.storage_backend_repo
        if not backends.get_by_name("VOS PGV"):
            backends.create(
                name="VOS PGV",
                kind="postgres",
                endpoint=f"{value['host']}:{value['port']}",
                access_key=value["user"],
                secret_key=value["password"],
                bucket=value["database"],
                region=value["schema"],
                note="VOS managed PostgreSQL; a separate ordinary role and database for this user.",
            )
    task = asyncio.create_task(refresh())
    try:
        app = build_app(server)
        app.title = "v-Octop API"
        app.version = os.environ.get("VOS_APP_VERSION", "0.0.0")
        await uvicorn.Server(
            uvicorn.Config(
                app, host="127.0.0.1", port=int(os.environ["VA_PORT"]), log_level="warning"
            )
        ).serve()
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
