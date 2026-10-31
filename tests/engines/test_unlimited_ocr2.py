"""Unlimited-OCR-2 (default model) vs. v1 inference paths."""

import json
from unittest.mock import MagicMock, patch

import pytest

from docfold.engines.base import OutputFormat
from docfold.engines.unlimited_ocr_engine import UnlimitedOCREngine


def _patched(model):
    return patch.object(UnlimitedOCREngine, "_ensure_model", return_value=(model, "tok"))


@pytest.fixture
def png(tmp_path):
    p = tmp_path / "a.png"
    p.write_bytes(b"\x89PNG fake")
    return str(p)


def test_default_model_is_v2():
    assert UnlimitedOCREngine()._model == "baidu/Unlimited-OCR-2"


@pytest.mark.asyncio
async def test_v2_single_page_uses_infer_without_v1_args(png):
    model = MagicMock()
    model.infer.return_value = "# one"
    with _patched(model):
        result = await UnlimitedOCREngine(device="cpu").process(png)
    assert result.content == "# one"
    kwargs = model.infer.call_args.kwargs
    assert kwargs["image_file"] == png
    assert kwargs["save_results"] is False
    assert "base_size" not in kwargs and "prompt" not in kwargs


@pytest.mark.asyncio
async def test_v2_multi_page_uses_infer_multi(tmp_path):
    model = MagicMock()
    model.infer_multi.return_value = ("<PAGE>first\n<PAGE>second", 42)
    e = UnlimitedOCREngine(device="cpu")
    with _patched(model), patch.object(
        UnlimitedOCREngine, "_to_image_paths", return_value=(["p1.png", "p2.png"], None)
    ):
        result = await e.process(str(tmp_path / "d.pdf"), OutputFormat.JSON)
    assert model.infer_multi.call_args.kwargs["image_files"] == ["p1.png", "p2.png"]
    assert [p["text"] for p in json.loads(result.content)["pages"]] == ["first", "second"]
    assert result.pages == 2


@pytest.mark.asyncio
async def test_v2_multi_page_unsplittable_output_kept_whole(tmp_path):
    model = MagicMock()
    model.infer_multi.return_value = ("no markers", 3)
    with _patched(model), patch.object(
        UnlimitedOCREngine, "_to_image_paths", return_value=(["p1.png", "p2.png"], None)
    ):
        result = await UnlimitedOCREngine(device="cpu").process(str(tmp_path / "d.pdf"))
    assert result.content == "no markers"
    assert result.pages == 2


@pytest.mark.asyncio
async def test_v1_keeps_mode_params(png):
    model = MagicMock()
    model.infer.return_value = "v1"
    with _patched(model):
        await UnlimitedOCREngine(model="baidu/Unlimited-OCR", device="cpu").process(png)
    kwargs = model.infer.call_args.kwargs
    assert (kwargs["base_size"], kwargs["image_size"], kwargs["crop_mode"]) == (1024, 640, True)
