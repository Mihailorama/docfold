"""Tests for the CLI module."""

import json

import pytest

import docfold
from docfold.cli import _build_router, main


class TestBuildRouter:
    def test_returns_router(self):
        router = _build_router()
        # Should return a router even if no engines are available
        from docfold.engines.router import EngineRouter
        assert isinstance(router, EngineRouter)

    def test_engines_list_is_list(self):
        router = _build_router()
        engines = router.list_engines()
        assert isinstance(engines, list)

    def test_registers_markitdown(self):
        # The adapter lazy-imports markitdown, so registration must succeed
        # even when the dependency is missing; is_available() gates selection.
        router = _build_router()
        assert router.get("markitdown") is not None


class TestMainNoArgs:
    def test_no_args_prints_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 0


class TestMainEngines:
    def test_engines_command(self, capsys):
        main(["engines"])
        captured = capsys.readouterr()
        assert "Engine" in captured.out or "No engines" in captured.out


class TestMainConvertArgs:
    def test_convert_missing_file_arg(self):
        with pytest.raises(SystemExit):
            main(["convert"])  # no file arg -> argparse error


class TestVersion:
    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        assert docfold.__version__ in capsys.readouterr().out


class TestDoctor:
    def test_doctor_json(self, capsys):
        main(["doctor", "--json"])
        report = json.loads(capsys.readouterr().out)
        assert report["version"] == docfold.__version__
        assert isinstance(report["mcp_extra"], bool)
        assert isinstance(report["engines"], dict)

    def test_doctor_text(self, capsys):
        main(["doctor"])
        out = capsys.readouterr().out
        assert docfold.__version__ in out
        assert "engines" in out


class TestInstall:
    def test_install_json_prints_generic_config(self, capsys):
        main(["install", "generic", "--json"])
        config = json.loads(capsys.readouterr().out)
        assert config["mcpServers"]["docfold"]["command"] == "docfold-mcp"

    def test_install_print_only_does_not_execute(self, capsys, monkeypatch):
        import subprocess

        def _boom(*a, **kw):
            raise AssertionError("must not execute in --print-only mode")

        monkeypatch.setattr(subprocess, "run", _boom)
        main(["install", "claude", "--print-only"])
        assert "docfold" in capsys.readouterr().out

    def test_install_unknown_client_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["install", "emacs"])
        assert exc_info.value.code != 0


class TestUpdate:
    def test_update_check_json(self, capsys, monkeypatch):
        from docfold import update as update_mod

        monkeypatch.setattr(update_mod, "latest_version", lambda: "999.0.0")
        main(["update", "--check", "--json"])
        report = json.loads(capsys.readouterr().out)
        assert report["current"] == docfold.__version__
        assert report["latest"] == "999.0.0"
        assert report["update_available"] is True

    def test_update_check_failure_exits_nonzero(self, capsys, monkeypatch):
        from docfold import update as update_mod

        def _boom():
            raise OSError("network down")

        monkeypatch.setattr(update_mod, "latest_version", _boom)
        with pytest.raises(SystemExit) as exc_info:
            main(["update", "--check"])
        assert exc_info.value.code != 0
