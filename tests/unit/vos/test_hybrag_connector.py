import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from octop.infra.vos import synchronize_hybrag_connector


@pytest.mark.asyncio
async def test_absent_hybrag_is_silent_then_connects_after_install(monkeypatch, tmp_path):
    monkeypatch.setenv("VA_SKILLS_DIR", "/product/skills")
    monkeypatch.setenv("HOME", str(tmp_path))
    available = False
    rows = []
    credentials = {}
    repo = MagicMock()
    repo.list_by_user.side_effect = lambda user_id: [row for row in rows if row.user_id == user_id]

    def create(**kwargs):
        rows.append(SimpleNamespace(**kwargs, status="active", shared=False))

    def status(instance_id, value):
        next(row for row in rows if row.instance_id == instance_id).status = value

    repo.create.side_effect = create
    repo.update_status.side_effect = status
    service = MagicMock()
    service.decrypt.side_effect = lambda instance_id: credentials.get(instance_id, {})
    service.encrypt_and_store.side_effect = lambda instance_id, payload: credentials.update(
        {instance_id: payload}
    )
    monkeypatch.setattr("octop.infra.connectors.service.ConnectorService", lambda **kwargs: service)

    def respond(request):
        assert request.url.path == "/api/v1/knowledge-bases"
        assert "authorization" not in request.headers
        return httpx.Response(200 if available else 503, json={"success": available, "data": []})

    monkeypatch.setattr("httpx.AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(respond))
    services = SimpleNamespace(
        repos=SimpleNamespace(connector_repo=repo),
        secret_repo=None,
        settings_repo=None,
        config=None,
    )
    await synchronize_hybrag_connector(services, 71)
    assert not rows
    available = True
    await synchronize_hybrag_connector(services, 71)
    assert len(rows) == 1 and rows[0].user_id == 71 and not rows[0].shared
    assert rows[0].display_name == "HybRAG"
    assert json.loads(rows[0].config_json)["default_open"] is True
    assert credentials[rows[0].instance_id] == {"base_url": "http://127.0.0.1", "vos_managed": True}
    await synchronize_hybrag_connector(services, 71)
    assert len(rows) == 1
    available = False
    await synchronize_hybrag_connector(services, 71)
    assert rows[0].status == "inactive"
    available = True
    await synchronize_hybrag_connector(services, 71)
    assert rows[0].status == "active" and len(rows) == 1
    rows[0].status = "disabled"
    await synchronize_hybrag_connector(services, 71)
    assert rows[0].status == "disabled"
