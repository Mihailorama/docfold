"""MiniCPM-OCR engine adapter — OpenBMB's document parser (layout + 1.3B OCR VLM).

Install: ``pip install "minicpm-ocr[all]"`` plus ``paddlepaddle`` (layout model),
see https://github.com/OpenBMB/MiniCPM-OCR/blob/main/docs/minicpm_ocr_tutorial_en.md

Full pages go through the SDK: PP-DocLayoutV3 finds regions, then the model
served by vLLM / SGLang / llama.cpp / Ollama reads each one.  The adapter calls
the SDK's documented ``minicpmvocr parse`` command::

    vllm serve openbmb/MiniCPM-OCR-1.0 --served-model-name minicpm-ocr ...
    export DOCFOLD_MINICPM_OCR_URL=http://localhost:18499/v1
    export DOCFOLD_MINICPM_OCR_BACKEND=llamacpp   # when served by llama-server

The layout model is downloaded once into ``~/.cache/docfold/minicpm-ocr``
(override with ``OCR_ASSETS_DIR``).  Model license: Apache-2.0.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat
from docfold.engines.vlm_ocr_engine import _format_output

_SUPPORTED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"}
_PAGE_BREAK = "\n\n<!-- page-break -->\n\n"  # the SDK's default page delimiter


class MiniCPMOCREngine(DocumentEngine):
    """Adapter for MiniCPM-OCR 1.0 via the ``minicpmvocr`` SDK."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str = "minicpm-ocr",
        device: str | None = None,
        backend: str | None = None,
        timeout: float = 3600,
    ) -> None:
        url = (base_url or os.getenv("DOCFOLD_MINICPM_OCR_URL") or "").rstrip("/")
        # The SDK appends /v1/chat/completions itself.
        self._base_url = url[:-3] if url.endswith("/v1") else url
        self._model = model
        self._device = device
        # vllm (SDK default) | llamacpp | ollama | openai
        self._backend = backend or os.getenv("DOCFOLD_MINICPM_OCR_BACKEND")
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "minicpm_ocr"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(table_structure=True, heading_detection=True, reading_order=True)

    def is_available(self) -> bool:
        return bool(self._base_url) and shutil.which("minicpmvocr") is not None

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        import asyncio

        start = time.perf_counter()
        markdown = await asyncio.get_running_loop().run_in_executor(None, self._run, file_path)
        pages = markdown.split(_PAGE_BREAK)
        content = markdown if output_format == OutputFormat.MARKDOWN else _format_output(
            pages, output_format)
        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            pages=len(pages),
            processing_time_ms=int((time.perf_counter() - start) * 1000),
            metadata={"model": self._model, "base_url": self._base_url},
        )

    def _run(self, file_path: str) -> str:
        cmd = [
            "minicpmvocr", "parse", str(Path(file_path).resolve()),
            "--server-url", self._base_url, "--model", self._model,
            "--stdout", "--page-delimiter", _PAGE_BREAK,
        ]
        if self._device:
            cmd += ["--device", self._device]
        if self._backend:
            cmd += ["--backend", self._backend]
        env = dict(os.environ)
        assets = env.setdefault(
            "OCR_ASSETS_DIR", str(Path.home() / ".cache" / "docfold" / "minicpm-ocr"))
        Path(assets).mkdir(parents=True, exist_ok=True)
        # ponytail: the run directory (and the region images markdown links to)
        # is discarded; keep OCR_RUN_ROOT if images are ever needed.
        with tempfile.TemporaryDirectory() as run_root:
            env["OCR_RUN_ROOT"] = run_root
            done = subprocess.run(cmd, capture_output=True, text=True, env=env,
                                  cwd=assets, timeout=self._timeout)
        if done.returncode != 0:
            raise RuntimeError(f"minicpmvocr parse failed: {done.stderr.strip()[-2000:]}")
        return done.stdout.strip()
