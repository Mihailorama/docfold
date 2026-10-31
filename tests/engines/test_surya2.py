"""Surya 2.x path (SuryaInferenceManager + full-page RecognitionPredictor)."""

import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from docfold.engines.base import OutputFormat
from docfold.engines.surya_engine import SuryaEngine


def _block(html, label="Text", order=0):
    return SimpleNamespace(html=html, label=label, reading_order=order,
                           polygon=[[0, 0], [1, 0], [1, 1], [0, 1]], confidence=0.9,
                           skipped=False)


@pytest.mark.asyncio
async def test_surya2_full_page_ocr(tmp_path):
    page = SimpleNamespace(blocks=[_block("<p>World</p>", order=1),
                                   _block("<h1>Hello &amp; hi</h1>", "SectionHeader", 0)])
    rec = MagicMock(return_value=[page])
    inference = ModuleType("surya.inference")
    inference.SuryaInferenceManager = MagicMock(return_value="mgr")
    recognition = ModuleType("surya.recognition")
    recognition.RecognitionPredictor = MagicMock(return_value=rec)
    mods = {"surya": ModuleType("surya"), "surya.inference": inference,
            "surya.recognition": recognition}
    with patch.dict(sys.modules, mods), \
         patch.object(SuryaEngine, "_load_images", return_value=["img"]):
        e = SuryaEngine()
        md = await e.process(str(tmp_path / "x.png"))
        js = await e.process(str(tmp_path / "x.png"), OutputFormat.JSON)
    recognition.RecognitionPredictor.assert_called_with("mgr")
    assert md.content.splitlines()[0] == "Hello & hi"
    assert "World" in md.content
    assert md.pages == 1
    line = json.loads(js.content)["pages"][0]["lines"][0]
    assert line["label"] == "SectionHeader"
    assert line["html"] == "<h1>Hello &amp; hi</h1>"
    assert line["confidence"] == 0.9
