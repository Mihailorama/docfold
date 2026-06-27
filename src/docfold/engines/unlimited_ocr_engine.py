"""Unlimited-OCR engine adapter — Baidu's one-shot long-horizon document parser.

Install: ``pip install docfold[unlimited-ocr]``

Unlimited-OCR is an open-weight document-parsing Vision-Language Model from
Baidu (released June 2026).  It takes DeepSeek-OCR as a baseline and replaces the
decoder's attention layers with **Reference Sliding Window Attention (R-SWA)**,
keeping a constant KV cache across decoding.  Combined with DeepSeek-OCR's
high-compression encoder, it can transcribe dozens of pages of a document in a
single forward pass under a 32K context window — the "one-shot long-horizon
parsing" capability that gives the project its name.

The model is loaded from HuggingFace (``baidu/Unlimited-OCR``) via
``trust_remote_code=True``; there is no separate pip package to import.

Two inference modes are supported, matching upstream:

- **gundam** (default) — ``base_size=1024, image_size=640, crop_mode=True``;
  dynamic cropping, best for single high-resolution images.
- **base** — ``base_size=1024, image_size=1024, crop_mode=False``; full
  resolution, best for multi-page documents.

Model & code license: MIT.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"}

# mode -> (base_size, image_size, crop_mode)
_MODE_PARAMS: dict[str, tuple[int, int, bool]] = {
    "gundam": (1024, 640, True),
    "base": (1024, 1024, False),
}

_DTYPE_MAP = {
    "bfloat16": "bfloat16",
    "float16": "float16",
    "float32": "float32",
}


class UnlimitedOCREngine(DocumentEngine):
    """Adapter for Baidu Unlimited-OCR (document → Markdown/HTML/JSON).

    Loads the ``baidu/Unlimited-OCR`` model from HuggingFace with
    ``trust_remote_code=True`` and runs ``model.infer`` per page.  PDFs are
    rendered to images (via PyMuPDF) before inference.

    See https://github.com/baidu/Unlimited-OCR
    """

    def __init__(
        self,
        mode: str = "gundam",
        model: str = "baidu/Unlimited-OCR",
        prompt: str = "<image>document parsing.",
        max_length: int = 32768,
        torch_dtype: str = "bfloat16",
        device: str = "cuda",
        dpi: int = 200,
    ) -> None:
        self._mode = mode
        self._model = model
        self._prompt = prompt
        self._max_length = max_length
        self._torch_dtype = torch_dtype
        self._device = device
        self._dpi = dpi
        # Lazily populated on first process() call.
        self._loaded_model: Any = None
        self._tokenizer: Any = None

    @property
    def name(self) -> str:
        return "unlimited_ocr"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            table_structure=True,
            heading_detection=True,
            reading_order=True,
        )

    def is_available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            from PIL import Image  # noqa: F401

            return True
        except Exception:
            return False

    def _mode_params(self) -> tuple[int, int, bool]:
        """Return ``(base_size, image_size, crop_mode)`` for the configured mode."""
        if self._mode not in _MODE_PARAMS:
            raise ValueError(
                f"Unknown mode '{self._mode}'. Choose one of: {sorted(_MODE_PARAMS)}"
            )
        return _MODE_PARAMS[self._mode]

    def _ensure_model(self) -> tuple[Any, Any]:
        """Lazy-load the model + tokenizer, caching them on the instance."""
        if self._loaded_model is not None and self._tokenizer is not None:
            return self._loaded_model, self._tokenizer

        import torch
        from transformers import AutoModel, AutoTokenizer

        dtype = getattr(torch, _DTYPE_MAP.get(self._torch_dtype, "bfloat16"))

        tokenizer = AutoTokenizer.from_pretrained(self._model, trust_remote_code=True)
        model = AutoModel.from_pretrained(
            self._model,
            trust_remote_code=True,
            use_safetensors=True,
            torch_dtype=dtype,
        )
        model = model.eval().to(self._device)

        self._loaded_model = model
        self._tokenizer = tokenizer
        return model, tokenizer

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        import asyncio

        start = time.perf_counter()

        loop = asyncio.get_running_loop()
        content, page_count = await loop.run_in_executor(
            None, self._do_process, file_path, output_format,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            pages=page_count,
            processing_time_ms=elapsed_ms,
            metadata={
                "model": self._model,
                "mode": self._mode,
                "max_length": self._max_length,
            },
        )

    def _do_process(
        self, file_path: str, output_format: OutputFormat,
    ) -> tuple[str, int]:
        import tempfile

        model, tokenizer = self._ensure_model()
        base_size, image_size, crop_mode = self._mode_params()

        image_paths, cleanup_dir = self._to_image_paths(file_path)
        try:
            pages_text: list[str] = []
            # ``output_path`` is required by infer for any side-effect output;
            # use a throwaway dir and rely on the returned text instead.
            with tempfile.TemporaryDirectory() as out_dir:
                for img_path in image_paths:
                    text = model.infer(
                        tokenizer,
                        prompt=self._prompt,
                        image_file=img_path,
                        output_path=out_dir,
                        base_size=base_size,
                        image_size=image_size,
                        crop_mode=crop_mode,
                        max_length=self._max_length,
                        save_results=False,
                    )
                    pages_text.append((text or "").strip())
        finally:
            if cleanup_dir is not None:
                cleanup_dir.cleanup()

        page_count = len(pages_text)
        content = self._format_output(pages_text, output_format)
        return content, page_count

    def _to_image_paths(self, file_path: str) -> tuple[list[str], Any]:
        """Return image file paths for the input plus an optional temp-dir handle.

        Images are used as-is.  PDFs are rendered page-by-page to PNG files in a
        :class:`tempfile.TemporaryDirectory`, returned as the second element so
        the caller can clean it up.
        """
        ext = Path(file_path).suffix.lstrip(".").lower()
        if ext != "pdf":
            return [file_path], None

        import tempfile

        tmp = tempfile.TemporaryDirectory()
        paths = self._render_pdf(file_path, tmp.name)
        return paths, tmp

    def _render_pdf(self, file_path: str, out_dir: str) -> list[str]:
        """Render each PDF page to a PNG file under *out_dir*."""
        import fitz  # PyMuPDF

        paths: list[str] = []
        doc = fitz.open(file_path)
        try:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=self._dpi)
                out_path = str(Path(out_dir) / f"page_{i + 1:04d}.png")
                pix.save(out_path)
                paths.append(out_path)
        finally:
            doc.close()
        return paths

    def _format_output(self, pages_text: list[str], output_format: OutputFormat) -> str:
        if output_format == OutputFormat.JSON:
            import json

            return json.dumps(
                {"pages": [{"page": i + 1, "text": t} for i, t in enumerate(pages_text)]},
                ensure_ascii=False,
            )

        if output_format == OutputFormat.HTML:
            html_parts = [
                f"<div class='page' data-page='{i + 1}'>{t}</div>"
                for i, t in enumerate(pages_text)
            ]
            return "<html><body>" + "\n".join(html_parts) + "</body></html>"

        # MARKDOWN / TEXT
        return "\n\n".join(pages_text)
