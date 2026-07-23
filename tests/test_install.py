"""Tests for one-click MCP registration — ``docfold install <client>``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from docfold import install


def test_server_entry_and_config() -> None:
    assert install.server_entry() == {"command": "docfold-mcp", "args": []}
    assert install.mcp_config() == {"mcpServers": {"docfold": install.server_entry()}}


def test_plan_claude_runs_cli_when_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install.shutil, "which", lambda _cmd: "/usr/bin/claude")
    plan = install.plan_install("claude")
    assert plan.kind == "run"
    assert plan.argv == ("claude", "mcp", "add", "docfold", "--", "docfold-mcp")


def test_plan_claude_prints_when_cli_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install.shutil, "which", lambda _cmd: None)
    plan = install.plan_install("claude")
    assert plan.kind == "print"
    assert plan.argv


def test_plan_codex_and_vscode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install.shutil, "which", lambda _cmd: "/usr/bin/x")
    assert install.plan_install("codex").argv[:3] == ("codex", "mcp", "add")
    vscode = install.plan_install("vscode")
    assert vscode.argv[0] == "code"
    assert "--add-mcp" in vscode.argv


def test_plan_cursor_targets_mcp_json(tmp_path: Path) -> None:
    plan = install.plan_install("cursor", home=tmp_path)
    assert plan.kind == "merge-json"
    assert plan.path == tmp_path / ".cursor" / "mcp.json"


def test_plan_generic_prints() -> None:
    assert install.plan_install("generic").kind == "print"


def test_plan_unknown_client_raises() -> None:
    with pytest.raises(ValueError, match="unknown client"):
        install.plan_install("emacs")


def test_merge_creates_file_when_missing(tmp_path: Path) -> None:
    path = tmp_path / ".cursor" / "mcp.json"
    assert install.merge_mcp_json(path) is True
    config = json.loads(path.read_text())
    assert config["mcpServers"]["docfold"] == install.server_entry()


def test_merge_preserves_foreign_servers(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": {"other": {"command": "other-mcp"}}}))
    assert install.merge_mcp_json(path) is True
    config = json.loads(path.read_text())
    assert config["mcpServers"]["other"] == {"command": "other-mcp"}
    assert config["mcpServers"]["docfold"] == install.server_entry()


def test_merge_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    assert install.merge_mcp_json(path) is True
    assert install.merge_mcp_json(path) is False


def test_merge_rejects_non_object_mcp_servers(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": ["not", "a", "dict"]}))
    with pytest.raises(ValueError):
        install.merge_mcp_json(path)


def test_apply_plan_print_only_does_not_execute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    called: list[object] = []
    monkeypatch.setattr(install.subprocess, "run", lambda *a, **kw: called.append(a))
    monkeypatch.setattr(install.shutil, "which", lambda _cmd: "/usr/bin/claude")

    plan = install.plan_install("claude")
    message = install.apply_plan(plan, print_only=True)
    assert "claude mcp add docfold" in message
    assert called == []

    cursor_plan = install.plan_install("cursor", home=tmp_path)
    message = install.apply_plan(cursor_plan, print_only=True)
    assert not (tmp_path / ".cursor" / "mcp.json").exists()
    assert "docfold" in message
