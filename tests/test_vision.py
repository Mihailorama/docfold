"""Injectable LLM caller for vision steps (DOCFOLD-17)."""

from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest

from docfold.engines.base import OutputFormat
from docfold.engines.vlm_ocr_engine import VLMOCREngine
from docfold.vision import caption_images


def _reply(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class Gateway:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return _reply(answer)


BIG = base64.b64encode(b"x" * 6000).decode()
TINY = base64.b64encode(b"x" * 10).decode()


async def test_vlm_ocr_uses_injected_gateway(tmp_path):
    img = tmp_path / "page.png"
    img.write_bytes(b"\x89PNG fake")
    gw = Gateway(["```markdown\n# Title\n```"])
    engine = VLMOCREngine("lighton_ocr", acompletion=gw)
    assert engine.is_available()
    res = await engine.process(str(img), model="openrouter/lighton-ocr")
    assert res.content == "# Title"
    call = gw.calls[0]
    assert call["model"] == "openrouter/lighton-ocr"
    assert call["messages"][-1]["content"][0]["image_url"]["url"].startswith("data:image/png")
    assert res.metadata["model"] == "openrouter/lighton-ocr"


async def test_vlm_ocr_default_model_and_postprocess(tmp_path):
    img = tmp_path / "p.jpg"
    img.write_bytes(b"jpeg")
    gw = Gateway(['[{"category": "Title", "text": "Hello"}]'])
    res = await VLMOCREngine("dots_ocr", acompletion=gw).process(
        str(img), output_format=OutputFormat.MARKDOWN
    )
    assert gw.calls[0]["model"] == "dots-studio/dots.ocr"
    assert "Hello" in res.content


async def test_caption_batches_filters_and_parses():
    gw = Gateway(["[logo.png]: Acme logo\n[chart.jpg]: Revenue 2024: 10, 2025: 12"])
    out = await caption_images(
        {"logo.png": BIG, "chart.jpg": BIG, "dot.png": TINY},
        ["vision-a"], acompletion=gw, document_text="Annual report",
    )
    assert out == {"logo.png": "Acme logo", "chart.jpg": "Revenue 2024: 10, 2025: 12"}
    assert len(gw.calls) == 1
    parts = gw.calls[0]["messages"][0]["content"]
    assert sum(p["type"] == "image_url" for p in parts) == 2
    # each image is preceded by its name, so the model can label its answer
    assert [p["text"] for p in parts[1:] if p["type"] == "text"] == ["[logo.png]", "[chart.jpg]"]
    assert "Annual report" in parts[0]["text"]


async def test_caption_single_image_takes_whole_answer():
    gw = Gateway(["A round stamp reading PAID"])
    assert await caption_images({"s.png": BIG}, ["m"], acompletion=gw) == {
        "s.png": "A round stamp reading PAID"
    }


async def test_caption_fallback_chain_and_failure():
    gw = Gateway([RuntimeError("429"), "[a.png]: ok\n[b.png]: fine"])
    out = await caption_images({"a.png": BIG, "b.png": BIG},
                               ["m1", {"model": "m2", "api_key": "k"}], acompletion=gw)
    assert out == {"a.png": "ok", "b.png": "fine"}
    assert [c["model"] for c in gw.calls] == ["m1", "m2"]
    assert gw.calls[1]["api_key"] == "k"
    gw = Gateway([RuntimeError("down")])
    assert await caption_images({"a.png": BIG}, ["m1"], acompletion=gw) == {"a.png": ""}


async def test_caption_nothing_eligible():
    assert await caption_images({"t.png": TINY}, ["m"], acompletion=Gateway([])) == {}
    with pytest.raises(ValueError):
        await caption_images({"a.png": BIG}, [], acompletion=Gateway([]))
