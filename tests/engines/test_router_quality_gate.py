"""Quality-gated fallback and per-attempt fallback_chain (DOCFOLD-11)."""

from __future__ import annotations

import pytest

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat
from docfold.engines.router import EngineRouter


class ScriptedEngine(DocumentEngine):
    """Returns fixed content, or raises when ``content`` is an exception."""

    def __init__(self, name, content, *, available=True, confidence=None, pages=1):
        self._name = name
        self._content = content
        self._available = available
        self._confidence = confidence
        self._pages = pages
        self.calls = 0

    @property
    def name(self):
        return self._name

    @property
    def supported_extensions(self):
        return {"pdf"}

    def is_available(self):
        return self._available

    async def process(self, file_path, output_format=OutputFormat.MARKDOWN, **kwargs):
        self.calls += 1
        if isinstance(self._content, Exception):
            raise self._content
        return EngineResult(
            content=self._content,
            format=output_format,
            engine_name=self._name,
            pages=self._pages,
            confidence=self._confidence,
            processing_time_ms=5,
        )


def short_gate(result, file_path):
    return None if len(result.content) >= 10 else "too_short"


async def test_chain_recorded_without_gate():
    router = EngineRouter([
        ScriptedEngine("a", RuntimeError("boom")),
        ScriptedEngine("b", "hello world"),
    ], fallback_order=["a", "b"])
    result = await router.process("x.pdf")
    assert result.engine_name == "b"
    chain = result.fallback_chain
    assert [a["engine"] for a in chain] == ["a", "b"]
    assert chain[0]["selected"] is False and "boom" in chain[0]["error"]
    assert chain[0]["role"] == "primary" and chain[1]["role"] == "fallback"
    assert chain[1]["selected"] is True
    assert chain[1]["chars"] == len("hello world")
    assert chain[1]["processing_time_ms"] == 5


async def test_gate_rejects_and_moves_on():
    b = ScriptedEngine("b", "long enough text here", confidence=0.9)
    router = EngineRouter([ScriptedEngine("a", "tiny"), b], fallback_order=["a", "b"])
    result = await router.process("x.pdf", quality_gate=short_gate)
    assert result.engine_name == "b"
    assert result.fallback_chain[0]["skip_reason"] == "too_short"
    assert result.fallback_chain[0]["selected"] is False
    assert result.fallback_chain[1]["confidence"] == 0.9


async def test_gate_passing_primary_stops_chain():
    b = ScriptedEngine("b", "other long text")
    router = EngineRouter([ScriptedEngine("a", "first long text"), b], fallback_order=["a", "b"])
    result = await router.process("x.pdf", quality_gate=short_gate)
    assert result.engine_name == "a"
    assert b.calls == 0
    assert len(result.fallback_chain) == 1


async def test_best_attempt_returned_when_nothing_passes():
    router = EngineRouter([
        ScriptedEngine("a", "abc"),
        ScriptedEngine("b", "abcdef"),
        ScriptedEngine("c", RuntimeError("down")),
    ], fallback_order=["a", "b", "c"])
    result = await router.process("x.pdf", quality_gate=short_gate)
    assert result.engine_name == "b"
    selected = [a["engine"] for a in result.fallback_chain if a["selected"]]
    assert selected == ["b"]


async def test_fallback_must_beat_earlier_text():
    # Primary fails the gate on something other than length; a shorter
    # fallback that passes is not an improvement (ai-utils rule).
    def gate(result, file_path):
        return "image_pages" if result.engine_name == "a" else None

    router = EngineRouter([
        ScriptedEngine("a", "x" * 50),
        ScriptedEngine("b", "y" * 20),
        ScriptedEngine("c", "z" * 80),
    ], fallback_order=["a", "b", "c"])
    result = await router.process("x.pdf", quality_gate=gate)
    assert result.engine_name == "c"
    assert result.fallback_chain[1]["selected"] is False


async def test_explicit_fallback_engines_after_hint():
    router = EngineRouter([
        ScriptedEngine("pymupdf", ""),
        ScriptedEngine("docling", "docling text output"),
        ScriptedEngine("marker", "marker text output, longer"),
        ScriptedEngine("docling_serve", "x", available=False),
    ])
    result = await router.process(
        "x.pdf",
        engine_hint="pymupdf",
        quality_gate=short_gate,
        fallback_engines=["docling_serve", "missing", "docling", "marker"],
    )
    assert result.engine_name == "docling"
    chain = result.fallback_chain
    assert [a["engine"] for a in chain] == ["pymupdf", "docling_serve", "missing", "docling"]
    assert chain[1]["skip_reason"] == "engine_unavailable"
    assert chain[2]["skip_reason"] == "engine_unavailable"


async def test_hint_without_fallbacks_still_raises():
    router = EngineRouter([ScriptedEngine("a", RuntimeError("boom")), ScriptedEngine("b", "ok")])
    with pytest.raises(RuntimeError, match="boom"):
        await router.process("x.pdf", engine_hint="a")


async def test_all_fail_raises():
    router = EngineRouter([
        ScriptedEngine("a", RuntimeError("one")),
        ScriptedEngine("b", RuntimeError("two")),
    ])
    with pytest.raises(RuntimeError, match="All engines failed"):
        await router.process("x.pdf", quality_gate=short_gate)


async def test_base64_images_do_not_count_as_text():
    img = '<img src="data:image/png;base64,' + "A" * 5000 + '"/>'
    router = EngineRouter([
        ScriptedEngine("a", "short" + img),
        ScriptedEngine("b", "real text that is long"),
    ], fallback_order=["a", "b"])
    result = await router.process("x.pdf", quality_gate=short_gate)
    assert result.fallback_chain[0]["chars"] == len("short")
