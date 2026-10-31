"""Engines whose OCR VLM needs a layout pass first: MiniCPM-OCR, GLM-OCR, PaddleOCR-VL.

Each talks to a vLLM/SGLang server given by ``DOCFOLD_<NAME>_URL`` (".../v1").
"""

import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from docfold.engines.base import OutputFormat


@pytest.fixture
def pdf(tmp_path):
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF-1.4")
    return str(p)


# --- MiniCPM-OCR (minicpmvocr CLI) -------------------------------------------

class TestMiniCPMOCR:
    def _engine(self, **kw):
        from docfold.engines.minicpm_ocr_engine import MiniCPMOCREngine
        return MiniCPMOCREngine(**kw)

    def test_name_and_exts(self):
        e = self._engine()
        assert e.name == "minicpm_ocr"
        assert {"pdf", "png", "jpg"} <= e.supported_extensions

    def test_unavailable_without_url_or_cli(self, monkeypatch):
        monkeypatch.delenv("DOCFOLD_MINICPM_OCR_URL", raising=False)
        assert self._engine().is_available() is False
        with patch("shutil.which", return_value=None):
            assert self._engine(base_url="http://x/v1").is_available() is False
        with patch("shutil.which", return_value="/bin/minicpmvocr"):
            assert self._engine(base_url="http://x/v1").is_available() is True

    @pytest.mark.asyncio
    async def test_runs_parse_cli(self, pdf, monkeypatch):
        monkeypatch.setenv("DOCFOLD_MINICPM_OCR_URL", "http://gpu:18499/v1/")
        done = SimpleNamespace(returncode=0, stdout="# A\n\n<!-- page-break -->\n\nB\n", stderr="")
        with patch("subprocess.run", return_value=done) as run:
            result = await self._engine(device="cpu").process(pdf)
        cmd = run.call_args.args[0]
        assert cmd[:3] == ["minicpmvocr", "parse", pdf]
        assert cmd[cmd.index("--server-url") + 1] == "http://gpu:18499"
        assert cmd[cmd.index("--model") + 1] == "minicpm-ocr"
        assert cmd[cmd.index("--device") + 1] == "cpu"
        assert "--stdout" in cmd
        assert "OCR_ASSETS_DIR" in run.call_args.kwargs["env"]
        assert result.content == "# A\n\n<!-- page-break -->\n\nB"
        assert result.pages == 2

    @pytest.mark.asyncio
    async def test_backend_flag(self, pdf, monkeypatch):
        monkeypatch.setenv("DOCFOLD_MINICPM_OCR_BACKEND", "llamacpp")
        done = SimpleNamespace(returncode=0, stdout="x", stderr="")
        with patch("subprocess.run", return_value=done) as run:
            await self._engine(base_url="http://x/v1").process(pdf)
            cmd = run.call_args.args[0]
            assert cmd[cmd.index("--backend") + 1] == "llamacpp"
            monkeypatch.delenv("DOCFOLD_MINICPM_OCR_BACKEND")
            await self._engine(base_url="http://x/v1").process(pdf)
            assert "--backend" not in run.call_args.args[0]

    @pytest.mark.asyncio
    async def test_cli_failure_raises(self, pdf):
        done = SimpleNamespace(returncode=2, stdout="", stderr="boom")
        with patch("subprocess.run", return_value=done), pytest.raises(RuntimeError, match="boom"):
            await self._engine(base_url="http://x/v1").process(pdf)


# --- GLM-OCR (glmocr SDK) ----------------------------------------------------

class TestGLMOCR:
    def _engine(self, **kw):
        from docfold.engines.glm_ocr_engine import GLMOCREngine
        return GLMOCREngine(**kw)

    def test_name(self):
        assert self._engine().name == "glm_ocr"

    def test_unavailable_without_url(self, monkeypatch):
        monkeypatch.delenv("DOCFOLD_GLM_OCR_URL", raising=False)
        assert self._engine().is_available() is False

    @pytest.mark.asyncio
    async def test_parses_with_selfhosted_sdk(self, pdf):
        parser = MagicMock()
        parser.parse.return_value = SimpleNamespace(
            markdown_result="# T", json_result=[[{"label": "text"}], [{"label": "title"}]],
        )
        glmocr = ModuleType("glmocr")
        glmocr.GlmOcr = MagicMock(return_value=parser)
        with patch.dict(sys.modules, {"glmocr": glmocr}):
            e = self._engine(base_url="http://gpu:8080/v1", layout_device="cpu")
            md = await e.process(pdf)
            js = await e.process(pdf, OutputFormat.JSON)
        kwargs = glmocr.GlmOcr.call_args.kwargs
        assert kwargs["mode"] == "selfhosted"
        assert kwargs["model"] == "glm-ocr"
        assert kwargs["layout_device"] == "cpu"
        assert kwargs["_dotted"] == {
            "pipeline.ocr_api.api_url": "http://gpu:8080/v1/chat/completions"
        }
        assert glmocr.GlmOcr.call_count == 1  # SDK pipeline is reused
        parser.parse.assert_called_with(pdf, save_layout_visualization=False)
        assert md.content == "# T"
        assert md.pages == 2
        assert json.loads(js.content)[1][0]["label"] == "title"


# --- PaddleOCR-VL (paddleocr.PaddleOCRVL) ------------------------------------

class TestPaddleOCRVL:
    def _engine(self, **kw):
        from docfold.engines.paddleocr_vl_engine import PaddleOCRVLEngine
        return PaddleOCRVLEngine(**kw)

    def test_name(self):
        assert self._engine().name == "paddleocr_vl"

    def test_does_not_shadow_classic_paddleocr(self):
        from docfold.engines.paddleocr_engine import PaddleOCREngine
        assert PaddleOCREngine().name != self._engine().name

    def test_unavailable_without_url(self, monkeypatch):
        monkeypatch.delenv("DOCFOLD_PADDLEOCR_VL_URL", raising=False)
        assert self._engine().is_available() is False

    @pytest.mark.asyncio
    async def test_predicts_via_vllm_server(self, pdf):
        pages = [SimpleNamespace(markdown={"markdown_texts": "# P1"}),
                 SimpleNamespace(markdown={"markdown_texts": "p2"})]
        pipeline = MagicMock()
        pipeline.predict.return_value = pages
        paddleocr = ModuleType("paddleocr")
        paddleocr.PaddleOCRVL = MagicMock(return_value=pipeline)
        with patch.dict(sys.modules, {"paddleocr": paddleocr}):
            e = self._engine(base_url="http://gpu:8080/v1/")
            md = await e.process(pdf)
            js = await e.process(pdf, OutputFormat.JSON)
        paddleocr.PaddleOCRVL.assert_called_once_with(
            pipeline_version="v1.6",
            vl_rec_backend="vllm-server",
            vl_rec_server_url="http://gpu:8080/v1",
            vl_rec_api_model_name=None,
        )
        assert md.content == "# P1\n\np2"
        assert md.pages == 2
        assert json.loads(js.content)["pages"][1] == {"page": 2, "text": "p2"}
