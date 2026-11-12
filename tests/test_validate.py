"""LLM validation of extracted text against the source (DOCFOLD-24)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from docfold.validate import validate_extraction

pymupdf = pytest.importorskip("pymupdf")


def _reply(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class Gateway:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    async def __call__(self, **kw):
        self.calls.append(kw)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return _reply(a)


def _pdf(path, pages=1):
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Total: 100 (page {i + 1})")
    doc.save(path)
    doc.close()
    return str(path)


ISSUE = {"type": "calculation_error", "severity": "major", "description": "10+20 != 40",
         "location": "table 1", "expected_value": "30", "actual_value": "40"}


async def test_consistency_and_visual(tmp_path):
    gw = Gateway([
        "```json\n" + json.dumps({"issues": [ISSUE]}) + "\n```",
        json.dumps({"issues": [{"type": "missing_content", "severity": "minor",
                                "description": "footer missing", "location": "page 1"}]}),
    ])
    res = await validate_extraction("| a | 10 |\n| b | 20 |\nTotal 40", ["m1"],
                                    file_path=_pdf(tmp_path / "a.pdf"), acompletion=gw,
                                    context="invoice")
    assert res.is_valid is False
    assert [i["source"] for i in res.issues] == ["consistency", "visual"]
    assert res.issues[0]["expected_value"] == "30"
    assert res.checks == ["consistency", "visual"]
    assert "invoice" in gw.calls[0]["messages"][0]["content"]
    visual = gw.calls[1]["messages"][0]["content"]
    assert any(p["type"] == "image_url" for p in visual)
    assert res.model == "m1"


async def test_minor_only_is_valid_and_visual_skipped_for_long_docs(tmp_path):
    gw = Gateway([json.dumps({"issues": [{**ISSUE, "severity": "minor"}]})])
    res = await validate_extraction("text", ["m"], file_path=_pdf(tmp_path / "b.pdf", 4),
                                    acompletion=gw, max_pages=3)
    assert res.is_valid is True
    assert res.checks == ["consistency"]
    assert "4 pages" in res.skipped["visual"]
    assert len(gw.calls) == 1


async def test_fallback_chain_and_all_fail():
    gw = Gateway([RuntimeError("429"), json.dumps({"issues": []})])
    res = await validate_extraction("ok", ["a", {"model": "b", "api_key": "k"}], acompletion=gw,
                                    visual=False)
    assert res.is_valid is True and res.model == "b"
    gw = Gateway([RuntimeError("down")])
    res = await validate_extraction("ok", ["a"], acompletion=gw, visual=False)
    assert res.is_valid is None and res.checks == [] and "down" in res.skipped["consistency"]


async def test_unparseable_answer(tmp_path):
    res = await validate_extraction("ok", ["a"], acompletion=Gateway(["not json"]), visual=False)
    assert res.is_valid is None and "consistency" in res.skipped
