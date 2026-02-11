"""Tests for the CLI module."""

import pytest
from unittest.mock import patch, AsyncMock
from docfold.cli import main, _build_router


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
