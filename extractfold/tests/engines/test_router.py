"""Tests for the ExtractionRouter."""

import os
from unittest.mock import patch

import pytest

from extractfold.engines.base import ExtractionEngine, ExtractionResult
from extractfold.engines.router import ExtractionRouter


class FakeEngine(ExtractionEngine):
    def __init__(self, name, extensions, available=True, fail=False):
        self._name = name
        self._extensions = extensions
        self._available = available
        self._fail = fail

    @property
    def name(self):
        return self._name

    @property
    def supported_extensions(self):
        return self._extensions

    def is_available(self):
        return self._available

    async def extract(self, file_path, schema, **kwargs):
        if self._fail:
            raise RuntimeError(f"{self._name} boom")
        return ExtractionResult(data={"by": self._name}, engine_name=self._name)


@pytest.fixture
def router():
    return ExtractionRouter([
        FakeEngine("lift", {"pdf", "png"}),
        FakeEngine("nuextract", {"pdf"}),
    ])


class TestSelect:
    def test_explicit_hint(self, router):
        assert router.select("a.pdf", engine_hint="nuextract").name == "nuextract"

    def test_explicit_hint_unknown(self, router):
        with pytest.raises(ValueError, match="Unknown engine"):
            router.select("a.pdf", engine_hint="nope")

    def test_explicit_hint_unavailable(self):
        r = ExtractionRouter([FakeEngine("broken", {"pdf"}, available=False)])
        with pytest.raises(RuntimeError, match="not available"):
            r.select("a.pdf", engine_hint="broken")

    def test_default_priority_picks_lift(self, router):
        with patch.dict(os.environ, {}, clear=True):
            assert router.select("a.pdf").name == "lift"

    def test_env_default(self, router):
        with patch.dict(os.environ, {"EXTRACT_ENGINE_DEFAULT": "nuextract"}):
            assert router.select("a.pdf").name == "nuextract"

    def test_extension_filter(self, router):
        # only lift supports png
        assert router.select("scan.png").name == "lift"

    def test_no_suitable_engine(self):
        r = ExtractionRouter([FakeEngine("pdf_only", {"pdf"})])
        with pytest.raises(ValueError, match="No available engine"):
            r.select("file.xyz")


class TestExtract:
    @pytest.mark.asyncio
    async def test_extract_delegates(self, router):
        result = await router.extract("a.pdf", {"type": "object"}, engine_hint="lift")
        assert result.engine_name == "lift"
        assert result.data == {"by": "lift"}

    @pytest.mark.asyncio
    async def test_extract_falls_back_on_failure(self):
        r = ExtractionRouter(
            [FakeEngine("lift", {"pdf"}, fail=True), FakeEngine("nuextract", {"pdf"})],
            fallback_order=["lift", "nuextract"],
        )
        result = await r.extract("a.pdf", {"type": "object"})
        assert result.engine_name == "nuextract"

    @pytest.mark.asyncio
    async def test_extract_hint_no_fallback(self):
        r = ExtractionRouter([FakeEngine("lift", {"pdf"}, fail=True)])
        with pytest.raises(RuntimeError, match="boom"):
            await r.extract("a.pdf", {"type": "object"}, engine_hint="lift")


class TestBatch:
    @pytest.mark.asyncio
    async def test_batch_mixed(self):
        r = ExtractionRouter(
            [FakeEngine("lift", {"pdf"})],
            fallback_order=["lift"],
        )
        batch = await r.extract_batch(["a.pdf", "b.xyz"], {"type": "object"})
        assert batch.total == 2
        assert batch.succeeded == 1
        assert batch.failed == 1
        assert "b.xyz" in batch.errors


class TestCompare:
    @pytest.mark.asyncio
    async def test_compare_all(self, router):
        results = await router.compare("a.pdf", {"type": "object"})
        assert set(results) == {"lift", "nuextract"}

    @pytest.mark.asyncio
    async def test_compare_subset(self, router):
        results = await router.compare("a.pdf", {"type": "object"}, engines=["lift"])
        assert set(results) == {"lift"}


class TestListEngines:
    def test_list(self, router):
        engines = router.list_engines()
        assert {e["name"] for e in engines} == {"lift", "nuextract"}
        for e in engines:
            assert "nested_schemas" in e["capabilities"]
            assert "provenance" in e["capabilities"]
