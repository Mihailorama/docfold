"""Tests for the generic OpenAI-compatible VLM OCR engine (presets)."""

import base64
import json
from unittest.mock import patch

import pytest

from docfold.engines.base import OutputFormat
from docfold.engines.vlm_ocr_engine import PRESETS, VLMOCREngine

PNG = b"\x89PNG\r\n\x1a\n fake"


def _reply(text):
    return {"choices": [{"message": {"content": text}}]}


@pytest.fixture
def png_file(tmp_path):
    p = tmp_path / "page.png"
    p.write_bytes(PNG)
    return str(p)


class TestPresets:
    def test_every_preset_has_model_and_prompt(self):
        assert set(PRESETS) == {"xiaomi_ocr", "hunyuan_ocr", "lighton_ocr", "ovis_ocr2", "dots_ocr"}
        for name, p in PRESETS.items():
            assert name == name.lower() and " " not in name
            assert "/" in p.model, name  # HF repo id
            assert isinstance(p.prompt, str), name

    def test_preset_names_do_not_shadow_native_engines(self):
        native = {"chandra", "surya", "mineru", "paddleocr", "unlimited_ocr",
                  "minicpm_ocr", "glm_ocr", "paddleocr_vl"}
        assert not native & set(PRESETS)

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError):
            VLMOCREngine("nope")


class TestEngine:
    def test_name_is_preset(self):
        assert VLMOCREngine("lighton_ocr").name == "lighton_ocr"

    def test_extensions(self):
        exts = VLMOCREngine("lighton_ocr").supported_extensions
        assert {"pdf", "png", "jpg", "webp"} <= exts

    def test_unavailable_without_url(self, monkeypatch):
        monkeypatch.delenv("DOCFOLD_LIGHTON_OCR_URL", raising=False)
        assert VLMOCREngine("lighton_ocr").is_available() is False

    def test_url_from_env(self, monkeypatch):
        monkeypatch.setenv("DOCFOLD_LIGHTON_OCR_URL", "http://gpu:8000/v1/")
        e = VLMOCREngine("lighton_ocr")
        assert e.is_available() is True
        assert e._base_url == "http://gpu:8000/v1"

    def test_overrides(self):
        e = VLMOCREngine("lighton_ocr", base_url="http://x/v1", model="m", prompt="p")
        assert (e._model, e._prompt) == ("m", "p")

    @pytest.mark.asyncio
    async def test_process_sends_image_and_prompt(self, png_file):
        e = VLMOCREngine("lighton_ocr", base_url="http://x/v1", api_key="k")
        with patch.object(VLMOCREngine, "_post", return_value=_reply("# Title")) as post:
            result = await e.process(png_file)
        assert result.content == "# Title"
        assert result.engine_name == "lighton_ocr"
        assert result.pages == 1
        assert result.metadata["model"] == PRESETS["lighton_ocr"].model
        url, payload, headers = post.call_args.args
        assert url == "http://x/v1/chat/completions"
        assert headers["Authorization"] == "Bearer k"
        parts = payload["messages"][-1]["content"]
        img = next(p for p in parts if p["type"] == "image_url")["image_url"]["url"]
        assert img == "data:image/png;base64," + base64.b64encode(PNG).decode()

    @pytest.mark.asyncio
    async def test_process_pdf_pages_json(self, tmp_path):
        fitz = pytest.importorskip("fitz")
        pdf = tmp_path / "two.pdf"
        doc = fitz.open()
        doc.new_page()
        doc.new_page()
        doc.save(str(pdf))
        doc.close()
        e = VLMOCREngine("lighton_ocr", base_url="http://x/v1")
        with patch.object(VLMOCREngine, "_post", side_effect=[_reply("a"), _reply("b")]):
            result = await e.process(str(pdf), OutputFormat.JSON)
        assert result.pages == 2
        assert [p["text"] for p in json.loads(result.content)["pages"]] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_strips_code_fence(self, png_file):
        e = VLMOCREngine("lighton_ocr", base_url="http://x/v1")
        with patch.object(VLMOCREngine, "_post", return_value=_reply("```markdown\nhi\n```")):
            result = await e.process(png_file)
        assert result.content == "hi"


class TestPresetSpecifics:
    @pytest.mark.asyncio
    async def test_hunyuan_sends_empty_system_and_extra_params(self, png_file):
        e = VLMOCREngine("hunyuan_ocr", base_url="http://x/v1")
        with patch.object(VLMOCREngine, "_post", return_value=_reply("t")) as post:
            await e.process(png_file)
        payload = post.call_args.args[1]
        assert payload["messages"][0] == {"role": "system", "content": ""}
        assert payload["repetition_penalty"] == 1.08
        text = next(p for p in payload["messages"][-1]["content"] if p["type"] == "text")
        assert text["text"].startswith("提取文档图片中正文")

    @pytest.mark.asyncio
    async def test_lighton_sends_image_only(self, png_file):
        e = VLMOCREngine("lighton_ocr", base_url="http://x/v1")
        with patch.object(VLMOCREngine, "_post", return_value=_reply("t")) as post:
            await e.process(png_file)
        parts = post.call_args.args[1]["messages"][-1]["content"]
        assert [p["type"] for p in parts] == ["image_url"]

    @pytest.mark.asyncio
    async def test_xiaomi_otsl_table_becomes_html(self, png_file):
        otsl = "# T\n\n<fcel>A<lcel><nl><fcel>1<fcel>2<nl>\n\nend"
        e = VLMOCREngine("xiaomi_ocr", base_url="http://x/v1")
        with patch.object(VLMOCREngine, "_post", return_value=_reply(otsl)):
            result = await e.process(png_file)
        assert result.content == (
            '# T\n\n<table><tr><td colspan="2">A</td></tr>'
            "<tr><td>1</td><td>2</td></tr></table>\n\nend"
        )

    def test_otsl_rowspan(self):
        from docfold.engines.vlm_ocr_engine import _otsl_to_html
        assert _otsl_to_html("<fcel>A<fcel>B<nl><ucel><fcel>C<nl>") == (
            '<table><tr><td rowspan="2">A</td><td>B</td></tr><tr><td>C</td></tr></table>'
        )

    @pytest.mark.asyncio
    async def test_dots_layout_json_becomes_markdown(self, png_file):
        layout = json.dumps([
            {"bbox": [0, 0, 1, 1], "category": "Page-header", "text": "hdr"},
            {"bbox": [0, 0, 1, 1], "category": "Title", "text": "# Title"},
            {"bbox": [0, 0, 1, 1], "category": "Picture"},
            {"bbox": [0, 0, 1, 1], "category": "Formula", "text": "x^2"},
            {"bbox": [0, 0, 1, 1], "category": "Text", "text": "body"},
        ])
        e = VLMOCREngine("dots_ocr", base_url="http://x/v1")
        with patch.object(VLMOCREngine, "_post", return_value=_reply(layout)) as post:
            result = await e.process(png_file)
        assert result.content == "# Title\n\n$$\nx^2\n$$\n\nbody"
        parts = post.call_args.args[1]["messages"][-1]["content"]
        text = next(p for p in parts if p["type"] == "text")
        assert text["text"].startswith("<|img|><|imgpad|><|endofimg|>Please output the layout")

    def test_dots_unparseable_reply_kept(self):
        from docfold.engines.vlm_ocr_engine import _dots_to_markdown
        assert _dots_to_markdown("not json") == "not json"
