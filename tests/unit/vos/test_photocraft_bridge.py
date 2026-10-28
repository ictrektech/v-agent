"""PhotoCraft state survives the harness's per-invocation bridge process."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

pytest.importorskip("fcntl")


def bridge():
    path = Path(__file__).parents[3] / "vos/photocraft_mcp.py"
    spec = importlib.util.spec_from_file_location("photocraft_bridge_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def upstream(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    sessions, files, observed = {}, {}, []

    def handle(request):
        observed.append(request)
        if request.url.path == "/volumes":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "data": [
                            {"adapter": "x_own", "name": "users/current/data"},
                        ]
                    },
                },
            )
        if request.url.path == "/upload":
            files[request.url.params["name"]] = request.read()
            return httpx.Response(200, json={"code": 0})
        if request.url.path == "/download":
            return httpx.Response(200, content=files[request.url.params["path"].split("://")[1]])
        body = json.loads(request.read())
        if body["method"] == "initialize":
            session = "session-" + str(len(observed))
            sessions[session] = None
            return httpx.Response(
                200,
                headers={"mcp-session-id": session},
                json={
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {"protocolVersion": "2025-03-26"},
                },
            )
        session = request.headers["mcp-session-id"]
        if session not in sessions:
            return httpx.Response(404)
        if body["method"].startswith("notifications/"):
            return httpx.Response(202)
        params = body["params"]
        if params["name"] == "doc_new":
            sessions[session] = params["arguments"]["name"]
        elif params["name"] == "doc_open":
            sessions[session] = params["arguments"]["path"]
        elif params["name"] == "doc_save":
            files[params["arguments"]["path"]] = files[sessions[session]]
        result = {
            "isError": False,
            "content": [{"type": "text", "text": str(sessions[session])}],
        }
        envelope = {"jsonrpc": "2.0", "id": body["id"], "result": result}
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text="data: \nid: 0\nretry: 3000\n\nevent: message\ndata: "
            + json.dumps(envelope)
            + "\n\n",
        )

    def load():
        module = bridge()
        module._client = lambda: httpx.Client(
            transport=httpx.MockTransport(handle), base_url="http://localhost"
        )
        return module

    return load, sessions, files, observed


def test_separate_bridge_instances_resume_the_document(upstream):
    load, sessions, _, observed = upstream
    load().native_request("tools/call", {"name": "doc_new", "arguments": {"name": "canary"}})
    result = load().native_request("tools/call", {"name": "session_list", "arguments": {}})
    assert "canary" in str(result)
    assert len(sessions) == 1
    assert sum(b'"method":"initialize"' in r.content for r in observed) == 1


def test_experts_have_separate_sessions(upstream, monkeypatch):
    load, sessions, _, _ = upstream
    for expert in ["expert-a", "expert-b"]:
        monkeypatch.setenv("VA_PHOTOCRAFT_SESSION_SCOPE", expert)
        load().native_request("tools/call", {"name": "doc_new", "arguments": {"name": expert}})
    assert set(sessions.values()) == {"expert-a", "expert-b"}
    monkeypatch.setenv("VA_PHOTOCRAFT_SESSION_SCOPE", "expert-a")
    assert "expert-a" in str(
        load().native_request("tools/call", {"name": "session_list", "arguments": {}})
    )


def test_expired_session_can_be_reinitialized(upstream):
    load, sessions, _, _ = upstream
    load().native_request("tools/call", {"name": "doc_new", "arguments": {"name": "old"}})
    sessions.clear()
    result = load().native_request("tools/call", {"name": "doc_new", "arguments": {"name": "new"}})
    assert "new" in str(result)


def test_workspace_import_and_export_use_raw_file_bytes(upstream, tmp_path):
    load, _, files, _ = upstream
    source, output = tmp_path / "input.png", tmp_path / "output.png"
    source.write_bytes(b"synthetic-png-fixture")
    imported = load()._import(str(source))
    assert files[imported["path"]] == source.read_bytes()
    exported = load()._export(str(output))
    assert output.read_bytes() == source.read_bytes()
    assert exported["bytes"] == source.stat().st_size
