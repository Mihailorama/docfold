"""Script detection and script-aware routing (DOCFOLD-12)."""

from __future__ import annotations

import sys
import types

import pytest

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat
from docfold.engines.router import EngineRouter
from docfold.utils import script as sc
from docfold.utils.script import ScriptHint, ScriptRouting, detect_script_hint


@pytest.mark.parametrize("text,hint", [
    ("The quick brown fox jumps over the lazy dog", ScriptHint.LATIN),
    ("Съешь же ещё этих мягких французских булок", ScriptHint.CYRILLIC),
    ("Invoice number 42 total amount due " * 3 + "فاتورة رقم", ScriptHint.ARABIC),
    ("שלום עולם זה מסמך בעברית עם טקסט", ScriptHint.ARABIC),
    ("Company profile and annual report " * 2 + "株式会社東京", ScriptHint.CJK),
    ("short", ScriptHint.UNKNOWN),
    ("", ScriptHint.UNKNOWN),
])
def test_detect_script_hint(text, hint):
    assert detect_script_hint(text) == hint


def _fake_tesseract(monkeypatch, osd=None, error=None):
    mod = types.ModuleType("pytesseract")

    def image_to_osd(path):
        if error:
            raise error
        return osd

    mod.image_to_osd = image_to_osd
    monkeypatch.setitem(sys.modules, "pytesseract", mod)


def test_osd(monkeypatch, tmp_path):
    _fake_tesseract(monkeypatch, osd="Page number: 0\nScript: Arabic\nScript confidence: 3.1")
    assert sc.detect_script_from_image(str(tmp_path / "x.png")) == ScriptHint.ARABIC
    _fake_tesseract(monkeypatch, osd="Script: Han\n")
    assert sc.detect_script_from_image("x.png") == ScriptHint.CJK
    _fake_tesseract(monkeypatch, error=RuntimeError("no tesseract"))
    assert sc.detect_script_from_image("x.png") == ScriptHint.UNKNOWN


def test_document_script_uses_text_then_osd(monkeypatch, tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    path = tmp_path / "scan.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    seen = []

    def osd(image_path):
        seen.append(image_path)
        return "Script: Cyrillic"

    mod = types.ModuleType("pytesseract")
    mod.image_to_osd = osd
    monkeypatch.setitem(sys.modules, "pytesseract", mod)
    assert sc.detect_document_script(str(path), "plain english text for routing") == (
        ScriptHint.LATIN
    )
    assert not seen
    assert sc.detect_document_script(str(path), "") == ScriptHint.CYRILLIC
    assert seen and seen[0].endswith(".png")


def _res(content, pages=1):
    return EngineResult(content=content, format=OutputFormat.TEXT, engine_name="pymupdf",
                        pages=pages)


def test_routing_chains():
    routing = ScriptRouting()
    arabic = "Invoice " * 10 + "فاتورة رقم واحد"
    assert routing(_res(arabic), "x.pdf") == (["marker"], {"script_hint": "arabic"})
    latin = "plain english text for routing " * 3
    assert routing(_res(latin, pages=3), "x.pdf")[0] == ["docling", "docling_serve", "marker"]
    assert routing(_res(latin, pages=9), "x.pdf")[0] == ["docling", "marker"]
    custom = ScriptRouting(rules={"cjk": ["paddleocr"]}, default=["tesseract"])
    assert custom(_res("株式会社東京 " * 5), "x.pdf")[0] == ["paddleocr"]
    assert custom(_res(latin), "x.pdf")[0] == ["tesseract"]


class Eng(DocumentEngine):
    def __init__(self, name, content):
        self._name, self._content = name, content

    @property
    def name(self):
        return self._name

    @property
    def supported_extensions(self):
        return {"pdf"}

    def is_available(self):
        return True

    async def process(self, file_path, output_format=OutputFormat.MARKDOWN, **kwargs):
        return EngineResult(content=self._content, format=output_format,
                            engine_name=self._name, pages=1)


async def test_router_calls_routing_only_on_failure():
    calls = []

    def plan(result, path):
        calls.append(result.engine_name if result else None)
        return ["marker"], {"script_hint": "arabic"}

    def gate(result, path):
        return "short" if len(result.content) < 20 else None

    router = EngineRouter([Eng("pymupdf", "فاتورة"), Eng("docling", "x" * 50),
                           Eng("marker", "y" * 40)])
    res = await router.process("x.pdf", engine_hint="pymupdf", quality_gate=gate,
                               fallback_engines=plan)
    assert res.engine_name == "marker"
    assert calls == ["pymupdf"]
    assert res.fallback_chain[0]["script_hint"] == "arabic"
    assert [a["engine"] for a in res.fallback_chain] == ["pymupdf", "marker"]

    calls.clear()
    ok = EngineRouter([Eng("pymupdf", "long enough primary text")])
    await ok.process("x.pdf", engine_hint="pymupdf", quality_gate=gate, fallback_engines=plan)
    assert calls == []
