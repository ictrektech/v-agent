import json

import httpx

from octop.infra.connectors.gateway.adapters import weknora


def test_managed_connector_uses_only_own_socket_and_never_forwards_tenant_override(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("VA_SKILLS_DIR", "/product/skills")
    monkeypatch.setenv("HOME", str(tmp_path))
    requests = []

    def respond(request):
        requests.append(request)
        assert "x-api-key" not in request.headers and "x-tenant-id" not in request.headers
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"success": True, "data": []})

    def transport(*, uds):
        assert uds == str(tmp_path / ".vagent" / "weknora.sock")
        return httpx.MockTransport(respond)

    monkeypatch.setattr("httpx.HTTPTransport", transport)
    creds = {
        "base_url": "http://127.0.0.1",
        "vos_managed": True,
        "api_key": "not-forwarded",
        "tenant_id": "not-forwarded",
    }
    result = json.loads(weknora.call_tool(creds, "list_knowledge_bases", {}))
    assert result == {"knowledge_bases": []}
    weknora.call_tool(creds, "list_documents", {"knowledge_base_id": "fixture", "page": 2})
    assert requests[-1].url.path == "/api/v1/knowledge-bases/fixture/knowledge"
    assert requests[-1].url.params["page"] == "2"
