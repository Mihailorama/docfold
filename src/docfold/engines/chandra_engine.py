"""Chandra OCR 2 engine adapter — Datalab's state-of-the-art document OCR model.

Install: ``pip install docfold[chandra]``

Chandra OCR 2 is a 5B-parameter Vision Language Model that converts images and
PDFs to structured Markdown, HTML, or JSON with layout preservation.  Supports
90+ languages, handwriting, tables, math, and complex layouts.

Supports two inference backends:
- **vLLM** (recommended): connect to a running ``chandra_vllm`` server
- **HuggingFace**: load the model locally via transformers

Model license: Modified OpenRAIL-M (free for research, personal use, and
startups <$2M funding/revenue).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"}


class ChandraEngine(DocumentEngine):
    """Adapter for Datalab Chandra OCR 2 (document → Markdown/HTML/JSON).

    Achieves 85.9% on the olmOCR benchmark — state of the art for open models.
    Excels at handwriting, forms, tables, math, and 90+ languages.

    See https://github.com/datalab-to/chandra
    """

    def __init__(
        self,
        method: str = "vllm",
        model: str = "datalab-to/chandra-ocr-2",
        prompt_type: str = "ocr_layout",
        vllm_url: str = "http://localhost:8000",
        torch_dtype: str = "bfloat16",
        device_map: str = "auto",
    ) -> None:
        self._method = method
        self._model = model
        self._prompt_type = prompt_type
        self._vllm_url = vllm_url
        self._torch_dtype = torch_dtype
        self._device_map = device_map
        self._hf_model: Any = None

    @property
    def name(self) -> str:
        return "chandra"

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
            import chandra  # noqa: F401
            if self._method == "hf":
                import torch  # noqa: F401
                import transformers  # noqa: F401
            return True
        except Exception:
            return False

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
            metadata={"model": self._model, "method": self._method},
        )

    def _do_process(
        self, file_path: str, output_format: OutputFormat,
    ) -> tuple[str, int]:
        from pathlib import Path

        from chandra.model.schema import BatchInputItem
        from chandra.output import parse_markdown
        from PIL import Image

        ext = Path(file_path).suffix.lstrip(".").lower()

        # Convert input to list of PIL images (one per page)
        images: list[Image.Image] = []
        if ext == "pdf":
            images = self._pdf_to_images(file_path)
        else:
            images = [Image.open(file_path)]

        # Build batch
        batch = [
            BatchInputItem(image=img, prompt_type=self._prompt_type)
            for img in images
        ]

        # Run inference
        if self._method == "vllm":
            results = self._infer_vllm(batch)
        else:
            results = self._infer_hf(batch)

        # Parse results
        pages_text: list[str] = []
        for result in results:
            md = parse_markdown(result.raw)
            pages_text.append(md)

        page_count = len(pages_text)
        full_text = "\n\n".join(pages_text)

        if output_format == OutputFormat.JSON:
            import json
            content = json.dumps(
                {"pages": [{"page": i + 1, "text": t} for i, t in enumerate(pages_text)]},
                ensure_ascii=False,
            )
        elif output_format == OutputFormat.HTML:
            html_parts = [
                f"<div class='page' data-page='{i + 1}'><p>{t}</p></div>"
                for i, t in enumerate(pages_text)
            ]
            content = "<html><body>" + "\n".join(html_parts) + "</body></html>"
        else:
            content = full_text

        return content, page_count

    def _pdf_to_images(self, file_path: str) -> list:
        """Convert PDF pages to PIL images."""
        from PIL import Image

        try:
            import fitz

            doc = fitz.open(file_path)
            images = []
            for page in doc:
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
            doc.close()
            return images
        except ImportError:
            pass

        from pdf2image import convert_from_path

        return convert_from_path(file_path, dpi=300)

    def _infer_vllm(self, batch: list) -> list:
        """Run inference via vLLM server."""
        from chandra.model import InferenceManager

        manager = InferenceManager(method="vllm", vllm_url=self._vllm_url)
        return manager.generate(batch)

    def _infer_hf(self, batch: list) -> list:
        """Run inference via HuggingFace transformers (lazy model loading)."""
        import torch
        from chandra.model.hf import generate_hf
        from transformers import AutoModelForImageTextToText, AutoProcessor

        if self._hf_model is None:
            dtype_map = {
                "bfloat16": torch.bfloat16,
                "float16": torch.float16,
                "float32": torch.float32,
            }
            dtype = dtype_map.get(self._torch_dtype, torch.bfloat16)

            model = AutoModelForImageTextToText.from_pretrained(
                self._model,
                dtype=dtype,
                device_map=self._device_map,
            )
            model.eval()
            model.processor = AutoProcessor.from_pretrained(self._model)
            model.processor.tokenizer.padding_side = "left"
            self._hf_model = model

        return generate_hf(batch, self._hf_model)
