"""MCP file downloads must preserve bytes and the caller's workspace boundary."""

import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "vos_mcp_download", Path(__file__).parents[3] / "vos" / "mcp_server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    response = Mock(status=200)
    response.read.return_value = b"\x89PNG\r\n\x1a\n\xff\x80\x00"
    response.getheader.return_value = "image/png"
    connection = Mock()
    connection.getresponse.return_value = response
    monkeypatch.setattr(module, "LocalConnection", lambda _: connection)
    return module, response, connection


def test_download_preserves_binary_bytes(bridge, tmp_path):
    module, response, connection = bridge
    result = module.request("image-studio", "GET", "/output", None, "generated/image.png")
    assert (tmp_path / "generated/image.png").read_bytes() == response.read.return_value
    assert result["bytes"] == len(response.read.return_value)
    assert "body" not in result
    connection.close.assert_called_once()


def test_binary_without_target_refuses_lossy_text(bridge):
    module, _, _ = bridge
    with pytest.raises(ValueError, match="specify output_file"):
        module.request("image-studio", "GET", "/output", None)


def test_download_rejects_escape_before_request(bridge, tmp_path):
    module, _, connection = bridge
    with pytest.raises(ValueError, match="current workspace"):
        module.request("image-studio", "GET", "/output", None, str(tmp_path.parent / "escape.png"))
    connection.request.assert_not_called()
