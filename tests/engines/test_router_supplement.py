"""Primary + supplement merge (DOCFOLD-13)."""

from __future__ import annotations

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat
from docfold.engines.router import EngineRouter


class Eng(DocumentEngine):
    def __init__(self, name, *, content="", boxes=None, images=None, meta=None,
                 tables=None, error=None, available=True, exts=("pdf",)):
        self._name, self._content, self._boxes = name, content, boxes
        self._images, self._meta, self._tables = images, meta or {}, tables
        self._error, self._available, self._exts = error, available, set(exts)
        self.calls = 0

    @property
    def name(self):
        return self._name

    @property
    def supported_extensions(self):
        return self._exts

    def is_available(self):
        return self._available

    async def process(self, file_path, output_format=OutputFormat.MARKDOWN, **kwargs):
        self.calls += 1
        if self._error:
            raise self._error
        return EngineResult(
            content=self._content, format=output_format, engine_name=self._name,
            pages=2, confidence=0.9 if self._name == "pymupdf" else 0.5,
            bounding_boxes=self._boxes, images=self._images, metadata=dict(self._meta),
            tables=self._tables, processing_time_ms=7,
        )


BOX = {"type": "Picture", "bbox": [0, 0, 10, 10], "page": 1, "text": "Company logo"}


def _router(marker, primary=None):
    primary = primary or Eng(
        "pymupdf", content="primary text " * 40,
        boxes=[{"type": "Text", "bbox": [1, 1, 2, 2], "page": 1}],
        meta={"source": "pymupdf"}, tables=[{"a": 1}],
    )
    return EngineRouter([primary, marker], fallback_order=["pymupdf", "marker"])


async def test_graft_layout_keep_primary_text():
    marker = Eng("marker", content="marker text", boxes=[BOX],
                 images={"p1.png": "aGk="}, meta={"marker_json": {"children": []}})
    res = await _router(marker).process("x.pdf", supplement_engine="marker")
    assert res.engine_name == "pymupdf"
    assert res.content.startswith("primary text")
    assert res.confidence == 0.9 and res.pages == 2 and res.processing_time_ms == 7
    assert res.bounding_boxes == [BOX]
    assert res.images == {"p1.png": "aGk="}
    assert res.metadata == {"source": "pymupdf", "marker_json": {"children": []}}
    assert res.tables == [{"a": 1}]
    sup = res.fallback_chain[-1]
    assert sup == {
        "engine": "marker", "chars": len("marker text"), "confidence": 0.5,
        "processing_time_ms": 7, "selected": False, "role": "bbox_supplement",
    }


async def test_skipped_when_supplement_is_primary():
    marker = Eng("marker", content="m " * 200, boxes=[BOX])
    router = EngineRouter([marker], fallback_order=["marker"])
    res = await router.process("x.pdf", supplement_engine="marker")
    assert marker.calls == 1
    assert [a["role"] for a in res.fallback_chain] == ["primary"]


async def test_supplement_failure_is_recorded_not_raised():
    marker = Eng("marker", error=RuntimeError("quota"))
    res = await _router(marker).process("x.pdf", supplement_engine="marker")
    assert res.engine_name == "pymupdf"
    assert res.bounding_boxes[0]["type"] == "Text"
    assert res.fallback_chain[-1]["role"] == "bbox_supplement"
    assert "quota" in res.fallback_chain[-1]["error"]


async def test_supplement_unavailable_or_unsupported():
    res = await _router(Eng("marker", available=False)).process(
        "x.pdf", supplement_engine="marker"
    )
    assert res.fallback_chain[-1]["skip_reason"] == "engine_unavailable"
    res = await _router(Eng("marker", exts=("docx",))).process(
        "x.pdf", supplement_engine="marker"
    )
    assert res.fallback_chain[-1]["skip_reason"] == "unsupported_extension"


async def test_no_boxes_from_supplement_keeps_primary_layout():
    marker = Eng("marker", content="m", boxes=None, images=None)
    res = await _router(marker).process("x.pdf", supplement_engine="marker")
    assert res.bounding_boxes == [{"type": "Text", "bbox": [1, 1, 2, 2], "page": 1}]
    assert res.images is None


async def test_with_quality_gate():
    def gate(result, path):
        return "short" if len(result.content) < 100 else None

    primary = Eng("pymupdf", content="tiny")
    docling = Eng("docling", content="docling text " * 20)
    marker = Eng("marker", content="m", boxes=[BOX])
    router = EngineRouter([primary, docling, marker])
    res = await router.process(
        "x.pdf", engine_hint="pymupdf", quality_gate=gate,
        fallback_engines=["docling"], supplement_engine="marker",
    )
    assert res.engine_name == "docling"
    assert res.bounding_boxes == [BOX]
    assert [a["role"] for a in res.fallback_chain] == ["primary", "fallback", "bbox_supplement"]
