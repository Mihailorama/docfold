"""Deskew, TrOCR engine and LLM OCR correction (DOCFOLD-21)."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from docfold.vision import correct_ocr_text

PIL = pytest.importorskip("PIL")
pytest.importorskip("numpy")
from PIL import Image, ImageDraw  # noqa: E402

from docfold.engines.trocr_engine import TrOCREngine, split_lines  # noqa: E402
from docfold.preprocessing.deskew import deskew_image, estimate_skew  # noqa: E402


def _page(lines=6):
    img = Image.new("L", (800, 600), 255)
    draw = ImageDraw.Draw(img)
    for i in range(lines):
        draw.rectangle((60, 60 + i * 70, 740, 80 + i * 70), fill=0)  # a "text line"
    return img


def test_estimate_and_fix_skew(tmp_path):
    page = _page()
    assert abs(estimate_skew(page)) < 0.3
    skewed = page.rotate(4, expand=True, fillcolor=255)
    angle = estimate_skew(skewed)
    assert -4.5 < angle < -3.5
    src = tmp_path / "s.png"
    skewed.save(src)
    out, a = deskew_image(str(src))
    assert out.endswith("s_deskewed.png") and a == angle
    assert abs(estimate_skew(Image.open(out))) < 0.5
    straight = tmp_path / "ok.png"
    page.save(straight)
    assert deskew_image(str(straight))[0] == str(straight)


def test_split_lines():
    spans = split_lines(_page(3).convert("RGB"))
    assert spans == [(60, 81), (130, 151), (200, 221)]


async def test_trocr_engine_with_fake_model(tmp_path, monkeypatch):
    path = tmp_path / "p.png"
    _page(2).convert("RGB").save(path)
    calls = []

    class Proc:
        @classmethod
        def from_pretrained(cls, mid):
            return cls()

        def __call__(self, images, return_tensors):
            calls.append(len(images))
            return SimpleNamespace(pixel_values=len(images))

        def batch_decode(self, ids, skip_special_tokens):
            return [f"line {i + 1}" for i in range(ids)]

    class Model:
        @classmethod
        def from_pretrained(cls, mid):
            return cls()

        def generate(self, pixel_values):
            return pixel_values

    fake = types.ModuleType("transformers")
    fake.TrOCRProcessor, fake.VisionEncoderDecoderModel = Proc, Model
    monkeypatch.setitem(sys.modules, "transformers", fake)
    res = await TrOCREngine().process(str(path))
    assert res.content == "line 1\nline 2" and res.pages == 1 and calls == [2]
    assert res.bounding_boxes[1]["bbox"] == [0, 130, 800, 151]


def _reply(t):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=t))])


async def test_correct_ocr_text():
    seen = []

    async def gw(**kw):
        seen.append(kw)
        if kw["model"] == "bad":
            raise RuntimeError("down")
        return _reply("Invoice total: 100")

    out = await correct_ocr_text("lnvoice tota1: 1OO", ["bad", "good"], acompletion=gw,
                                 image_b64="aGk=")
    assert out == "Invoice total: 100"
    assert seen[1]["messages"][0]["content"][1]["type"] == "image_url"

    async def down(**kw):
        raise RuntimeError("x")

    assert await correct_ocr_text("keep me", ["m"], acompletion=down) == "keep me"
