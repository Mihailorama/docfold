"""Tests for self-update helpers — ``docfold update``."""

from __future__ import annotations

import io
import json
import sys

import pytest

from docfold import update


def test_is_newer() -> None:
    assert update.is_newer("0.7.1", "0.7.0") is True
    assert update.is_newer("0.7.0", "0.7.0") is False
    assert update.is_newer("0.6.9", "0.7.0") is False
    assert update.is_newer("1.0.0", "0.99.99") is True


def test_build_update_argv_plain() -> None:
    assert update.build_update_argv() == [
        sys.executable, "-m", "pip", "install", "--upgrade", "docfold",
    ]


def test_build_update_argv_with_extras() -> None:
    argv = update.build_update_argv("mcp, docling")
    assert argv[-1] == "docfold[mcp,docling]"


def test_build_update_argv_blank_extras() -> None:
    assert update.build_update_argv(" , ")[-1] == "docfold"


def test_latest_version_parses_pypi_json(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps({"info": {"version": "0.9.9"}}).encode()

    def _fake_urlopen(url: str, timeout: float = 10.0):
        assert "pypi.org/pypi/docfold/json" in url
        return io.BytesIO(body)

    monkeypatch.setattr(update, "urlopen", _fake_urlopen)
    assert update.latest_version() == "0.9.9"
