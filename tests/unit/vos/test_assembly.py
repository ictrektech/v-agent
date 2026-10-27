"""VOS capabilities are opt-in and remain local to a tenant process."""

from octop.infra.vos import add_vos_capabilities


def test_upstream_runtime_is_unchanged_without_vos(monkeypatch):
    monkeypatch.delenv("VA_SKILLS_DIR", raising=False)
    skills, servers = ["custom"], {"external": {"transport": "http"}}
    assert add_vos_capabilities(skills, servers) == (skills, servers)


def test_vos_assembly_keeps_custom_connectors_and_uses_local_stdio(monkeypatch):
    monkeypatch.setenv("VA_SKILLS_DIR", "/product/skills")
    custom = {"external": {"transport": "http", "url": "https://example.invalid"}}
    skills, servers = add_vos_capabilities(["custom"], custom)
    assert skills == ["custom", "/product/skills"]
    assert servers["external"] == custom["external"]
    assert servers["vos-apps"]["transport"] == "stdio"
    assert "vos-apps" not in custom
