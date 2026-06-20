"""Tests for the Lift engine adapter.

These run without ``lift-pdf`` installed by stubbing the ``lift`` module.
Real end-to-end runs require a GPU / vLLM server and are marked ``integration``.
"""

import sys
import types
from unittest.mock import MagicMock

import pytest

from extractfold.engines.lift_engine import LiftEngine


class TestMetadata:
    def test_name(self):
        assert LiftEngine().name == "lift"

    def test_supported_extensions(self):
        ext = LiftEngine().supported_extensions
        assert "pdf" in ext
        assert "png" in ext

    def test_capabilities_vllm_is_remote(self):
        caps = LiftEngine(method="vllm").capabilities
        assert caps.remote is True
        assert caps.local is False
        assert caps.nested_schemas is True

    def test_capabilities_hf_is_local(self):
        caps = LiftEngine(method="hf").capabilities
        assert caps.local is True
        assert caps.remote is False


class TestAvailability:
    def test_unavailable_without_lift(self):
        # lift-pdf is not installed in CI
        assert LiftEngine().is_available() is False

    @pytest.mark.asyncio
    async def test_extract_raises_when_unavailable(self):
        with pytest.raises(RuntimeError, match="not available"):
            await LiftEngine().extract("doc.pdf", {"type": "object"})


class TestExtractWithStub:
    """Drive the adapter against a fake ``lift`` module."""

    @pytest.fixture
    def fake_lift(self, monkeypatch):
        lift_mod = types.ModuleType("lift")
        model_mod = types.ModuleType("lift.model")

        class FakeResult:
            extraction = {"invoice_number": "A-1", "total": 99.5}
            page_count = 2
            token_count = 1234
            error = None
            raw = '{"invoice_number": "A-1", "total": 99.5}'

        extract_mock = MagicMock(return_value=FakeResult())
        lift_mod.extract = extract_mock
        model_mod.InferenceManager = MagicMock(name="InferenceManager")
        lift_mod.model = model_mod

        monkeypatch.setitem(sys.modules, "lift", lift_mod)
        monkeypatch.setitem(sys.modules, "lift.model", model_mod)
        return extract_mock

    @pytest.mark.asyncio
    async def test_extract_maps_result(self, fake_lift):
        engine = LiftEngine(method="vllm")
        result = await engine.extract("invoice.pdf", {"type": "object"})

        assert result.engine_name == "lift"
        assert result.data == {"invoice_number": "A-1", "total": 99.5}
        assert result.pages == 2
        assert result.metadata["token_count"] == 1234
        assert result.metadata["method"] == "vllm"
        assert result.schema == {"type": "object"}
        assert result.raw is not None

    @pytest.mark.asyncio
    async def test_extract_passes_page_range_and_tokens(self, fake_lift):
        engine = LiftEngine(method="vllm")
        await engine.extract(
            "invoice.pdf", {"type": "object"}, page_range="0-3", max_output_tokens=512,
        )
        _, kwargs = fake_lift.call_args
        assert kwargs["page_range"] == "0-3"
        assert kwargs["max_output_tokens"] == 512

    @pytest.mark.asyncio
    async def test_extract_raises_on_none_extraction(self, monkeypatch):
        lift_mod = types.ModuleType("lift")
        model_mod = types.ModuleType("lift.model")

        class EmptyResult:
            extraction = None
            error = "parse failure"

        lift_mod.extract = MagicMock(return_value=EmptyResult())
        model_mod.InferenceManager = MagicMock()
        lift_mod.model = model_mod
        monkeypatch.setitem(sys.modules, "lift", lift_mod)
        monkeypatch.setitem(sys.modules, "lift.model", model_mod)

        with pytest.raises(RuntimeError, match="no extraction"):
            await LiftEngine(method="vllm").extract("bad.pdf", {"type": "object"})


@pytest.mark.integration
class TestLiftIntegration:
    """Real model runs — require `pip install extractfold[lift]` and a GPU/vLLM server."""

    @pytest.mark.asyncio
    async def test_real_extraction(self):
        engine = LiftEngine()
        if not engine.is_available():
            pytest.skip("lift-pdf not installed")
        # Provide a real fixture document + schema to exercise end-to-end.
        pytest.skip("Add a sample document fixture to run the real model.")
