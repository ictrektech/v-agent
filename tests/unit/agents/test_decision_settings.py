"""Decision-model settings stay off until an endpoint is saved."""

from __future__ import annotations

from pathlib import Path

import pytest

from octop.infra.agents.settings.decision import DecisionSettingsStore
from octop.infra.db.migrate import run_migrations
from octop.infra.db.pool import SqlitePool
from octop.infra.db.repos.secrets import SecretRepo
from octop.infra.db.repos.settings import SettingsRepo
from octop.infra.errors import OctopError


@pytest.fixture
def store(tmp_path: Path) -> DecisionSettingsStore:
    db = SqlitePool(tmp_path / "octop.db")
    run_migrations(db)
    return DecisionSettingsStore(settings_repo=SettingsRepo(db), secret_repo=SecretRepo(db))


def test_decision_settings_default_off(store: DecisionSettingsStore) -> None:
    view = store.load()
    assert view.enabled is False
    assert view.active is False
    assert view.tools is False
    assert store.harness_config() is None


def test_decision_settings_roundtrip(store: DecisionSettingsStore) -> None:
    saved = store.save(
        enabled=True,
        provider="jev",
        endpoint="https://openrouter.ai/api/alpha/decisions",
        model="typesafe/jev-1.13",
        skills=True,
        tools=False,
        team=True,
        threshold=0.7,
        tool_min_count=10,
        api_key="sk-test",
    )
    assert saved.active is True
    assert saved.api_key_set is True
    assert saved.tools is False

    raw = store._secrets.get("decision_api_key:jev")  # noqa: SLF001
    assert raw is not None
    assert raw != b"sk-test"
    assert raw.startswith(b"gAAAA")

    config = store.harness_config()
    assert config is not None
    assert config.enabled is True
    assert config.api_key == "sk-test"
    assert config.model == "typesafe/jev-1.13"
    assert config.api_key == "sk-test"
    assert config.tools is False

    kept = store.save(
        enabled=False,
        provider="jev",
        endpoint="https://openrouter.ai/api/alpha/decisions",
        model="typesafe/jev-1.13",
        skills=True,
        tools=True,
        team=True,
        threshold=0.7,
        tool_min_count=10,
    )
    assert kept.api_key_set is True
    assert store.harness_config() is None


def test_decision_settings_preserves_custom_provider(store: DecisionSettingsStore) -> None:
    saved = store.save(
        enabled=True,
        provider="custom",
        endpoint="https://decision.example.test/v1/score",
        model="private-router",
        skills=True,
        tools=True,
        team=False,
        threshold=0.6,
        tool_min_count=8,
    )
    assert saved.provider == "custom"
    config = store.harness_config()
    assert config is not None
    assert config.provider == "custom"


def test_decision_settings_clears_key_when_endpoint_changes(store: DecisionSettingsStore) -> None:
    store.save(
        enabled=True,
        provider="jev",
        endpoint="https://one.example.test/decisions",
        model="typesafe/jev-1.13",
        skills=True,
        tools=True,
        team=True,
        threshold=0.6,
        tool_min_count=8,
        api_key="secret-for-one",
    )
    saved = store.save(
        enabled=True,
        provider="custom",
        endpoint="https://two.example.test/decisions",
        model="",
        skills=True,
        tools=True,
        team=True,
        threshold=0.6,
        tool_min_count=8,
    )
    assert saved.api_key_set is False
    config = store.harness_config()
    assert config is not None
    assert config.api_key == ""
    jev = next(item for item in saved.services if item.provider == "jev")
    assert jev.api_key_set is True
    assert jev.endpoint == "https://one.example.test/decisions"


def test_decision_settings_keeps_every_service(store: DecisionSettingsStore) -> None:
    store.save(
        enabled=True,
        provider="laya",
        endpoint="http://127.0.0.1:8000/v1/systemone",
        model="",
        skills=True,
        tools=True,
        team=True,
        threshold=0.6,
        tool_min_count=8,
        services=[
            {
                "provider": "jev",
                "endpoint": "https://openrouter.ai/api/alpha/decisions",
                "model": "typesafe/jev-1.13",
                "api_key": "jev-key",
            },
            {
                "provider": "laya",
                "endpoint": "http://127.0.0.1:8000/v1/systemone",
                "model": "",
                "api_key": "",
            },
        ],
    )
    saved = store.save(
        enabled=True,
        provider="jev",
        endpoint="https://openrouter.ai/api/alpha/decisions",
        model="typesafe/jev-1.13",
        skills=True,
        tools=True,
        team=True,
        threshold=0.6,
        tool_min_count=8,
        services=[
            {
                "provider": "jev",
                "endpoint": "https://openrouter.ai/api/alpha/decisions",
                "model": "typesafe/jev-1.13",
                "api_key": None,
            },
            {
                "provider": "laya",
                "endpoint": "http://127.0.0.1:8000/v1/systemone",
                "model": "",
                "api_key": None,
            },
        ],
    )
    assert saved.provider == "jev"
    assert saved.endpoint == "https://openrouter.ai/api/alpha/decisions"
    laya = next(item for item in saved.services if item.provider == "laya")
    assert laya.endpoint == "http://127.0.0.1:8000/v1/systemone"
    config = store.harness_config()
    assert config is not None
    assert config.provider == "jev"
    assert config.api_key == "jev-key"


def test_decision_settings_requires_endpoint_and_model(store: DecisionSettingsStore) -> None:
    with pytest.raises(OctopError):
        store.save(
            enabled=True,
            provider="jev",
            endpoint="",
            model="typesafe/jev-1.13",
            skills=True,
            tools=True,
            team=True,
            threshold=0.6,
            tool_min_count=8,
        )
    with pytest.raises(OctopError):
        store.save(
            enabled=True,
            provider="jev",
            endpoint="https://openrouter.ai/api/alpha/decisions",
            model="",
            skills=True,
            tools=True,
            team=True,
            threshold=0.6,
            tool_min_count=8,
        )


async def test_probe_reports_when_the_endpoint_is_down(
    store: DecisionSettingsStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Down:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def score_async(self, **_kwargs: object) -> dict[str, float]:
            raise ConnectionError("All connection attempts failed")

    monkeypatch.setattr("octop_harness.decision.client.HttpDecisionClient", _Down)
    result = await store.probe(
        endpoint="http://127.0.0.1:8000/v1/systemone",
        api_key="",
        model="",
        provider="laya",
    )
    assert result["ok"] is False
    assert "8000" in str(result["error"])
    assert "no probability" not in str(result["error"])


async def test_probe_does_not_send_saved_key_to_another_endpoint(
    store: DecisionSettingsStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.save(
        enabled=True,
        provider="jev",
        endpoint="https://one.example.test/decisions",
        model="typesafe/jev-1.13",
        skills=True,
        tools=True,
        team=True,
        threshold=0.6,
        tool_min_count=8,
        api_key="secret-for-one",
    )
    seen: dict[str, object] = {}

    class _Probe:
        def __init__(self, **kwargs: object) -> None:
            seen.update(kwargs)

        async def score_async(self, **_kwargs: object) -> dict[str, float]:
            return {"ping": 0.9}

    monkeypatch.setattr("octop_harness.decision.client.HttpDecisionClient", _Probe)
    result = await store.probe(
        endpoint="https://two.example.test/decisions",
        api_key=None,
        model="",
        provider="custom",
    )
    assert result["ok"] is True
    assert seen["api_key"] == ""


def test_scheduler_is_an_additional_independent_service(store: DecisionSettingsStore) -> None:
    args = {
        "enabled": True,
        "skills": True,
        "tools": False,
        "team": True,
        "threshold": 0.6,
        "tool_min_count": 8,
    }
    store.save(
        provider="jev",
        endpoint="https://vendor.invalid/decisions",
        model="jev-original",
        api_key="vendor-key",
        **args,
    )
    view = store.save(
        provider="jev",
        endpoint="https://vendor.invalid/decisions",
        model="jev-original",
        services=[
            {
                "provider": "scheduler",
                "endpoint": "http://scheduler/v1/systemone",
                "model": "tev1:4b",
                "api_key": "scoped-key",
            }
        ],
        **args,
    )
    assert view.provider == "jev"
    assert store.harness_config().api_key == "vendor-key"
    assert (
        next(service for service in view.services if service.provider == "jev").model
        == "jev-original"
    )
    assert {service.provider for service in view.services} == {
        "jev",
        "microsoft",
        "laya",
        "custom",
        "scheduler",
    }
    view = store.save(
        provider="scheduler", endpoint="http://scheduler/v1/systemone", model="tev1:4b", **args
    )
    config = store.harness_config()
    assert config.provider == "jev"
    assert config.model == "tev1:4b"
    assert config.api_key == "scoped-key"
    assert (
        next(service for service in view.services if service.provider == "jev").endpoint
        == "https://vendor.invalid/decisions"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_managed", [False, True])
async def test_vos_discovery_keeps_existing_default_and_vendor_service(
    store, monkeypatch, legacy_managed
):
    import importlib.util
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    spec = importlib.util.spec_from_file_location(
        "vos_runtime_test", Path(__file__).parents[3] / "vos/runtime.py"
    )
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    store.save(
        enabled=True,
        provider="jev",
        endpoint="http://scheduler/v1/systemone"
        if legacy_managed
        else "https://vendor.invalid/decisions",
        model="jev-original",
        skills=True,
        tools=False,
        team=True,
        threshold=0.6,
        tool_min_count=8,
        api_key="vendor-key",
    )
    monkeypatch.setenv("VA_SCHEDULER_URL", "http://scheduler")
    monkeypatch.setenv("VA_SCHEDULER_KEY", "scoped-key")
    monkeypatch.setattr(
        runtime,
        "catalog",
        lambda: [
            {
                "id": "tev1:4b",
                "name": "Tev1",
                "api": "openai-completions",
                "categories": ["decision"],
                "endpoints": ["systemone"],
            }
        ],
    )
    registry = MagicMock()
    registry.decision = store
    registry.save_decision = AsyncMock(side_effect=store.save)
    registry.list_agents.return_value = []
    server = MagicMock()
    server.services.provider_repo.get_by_name.return_value = None
    server.services.settings_repo = store._settings
    server.services.voice_provider_repo.list_all.return_value = []
    server.app_runtime.agent_registry = registry
    server.user_manager.get.return_value = SimpleNamespace(id=1)
    await runtime.synchronize(server)
    assert store.load().provider == ("scheduler" if legacy_managed else "jev")
    assert store.harness_config().api_key == ("scoped-key" if legacy_managed else "vendor-key")
    assert (
        next(service for service in store.load().services if service.provider == "scheduler").model
        == "tev1:4b"
    )
