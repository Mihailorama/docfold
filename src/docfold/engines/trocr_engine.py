"""TrOCR engine (Microsoft's transformer OCR) for printed or handwritten text.

TrOCR reads one text line per call, so pages are cut into lines first with a
horizontal projection profile. Install: ``pip install docfold[trocr]``
(transformers + torch + Pillow; PyMuPDF for PDFs). The model downloads from
Hugging Face on first use.
"""

from __future__ import annotations

import asyncio
import io
import time
from pathlib import Path
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

_IMAGES = {"png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"}


def split_lines(image: Any, min_gap: int = 3, min_height: int = 8) -> list[tuple[int, int]]:
    """``(top, bottom)`` pixel rows of text lines in a page image (PIL), top to bottom."""
    import numpy as np

    ink = [int(v) for v in (np.asarray(image.convert("L")) < 160).sum(axis=1)]
    threshold = max(1, int(max(ink, default=0) * 0.02))
    rows = [v >= threshold for v in ink]
    lines, start, gap = [], None, 0
    for y, on in enumerate(rows):
        if on:
            start = y if start is None else start
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                if y - gap - start + 1 >= min_height:
                    lines.append((start, y - gap + 1))
                start, gap = None, 0
    if start is not None and len(rows) - start >= min_height:
        lines.append((start, len(rows)))
    return lines


class TrOCREngine(DocumentEngine):
    """Line-by-line OCR with a TrOCR checkpoint (default ``microsoft/trocr-base-printed``).

    Per-page lines become paragraphs; each line also becomes a ``Line``
    bounding box in image pixels of the rendered page (``dpi``).
    """

    def __init__(
        self,
        model: str = "microsoft/trocr-base-printed",
        dpi: int = 200,
        batch_size: int = 16,
        device: str | None = None,
    ) -> None:
        self._model_id = model
        self._dpi = dpi
        self._batch = batch_size
        self._device = device
        self._loaded: tuple[Any, Any] | None = None

    @property
    def name(self) -> str:
        return "trocr"

    @property
    def supported_extensions(self) -> set[str]:
        return _IMAGES | {"pdf"}

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(bounding_boxes=True)

    def is_available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            from PIL import Image  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        start = time.perf_counter()
        pages, boxes = await asyncio.get_running_loop().run_in_executor(
            None, self._run, file_path
        )
        if output_format == OutputFormat.JSON:
            import json

            content = json.dumps({"pages": [{"page": i + 1, "lines": p}
                                            for i, p in enumerate(pages)]}, ensure_ascii=False)
        else:
            content = "\n\n".join("\n".join(p) for p in pages)
        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            pages=len(pages),
            bounding_boxes=boxes,
            processing_time_ms=int((time.perf_counter() - start) * 1000),
            metadata={"model": self._model_id, "dpi": self._dpi},
        )

    def _images(self, file_path: str) -> list[Any]:
        from PIL import Image

        if Path(file_path).suffix.lstrip(".").lower() != "pdf":
            return [Image.open(file_path).convert("RGB")]
        from docfold.render import render_pages

        return [Image.open(io.BytesIO(data)).convert("RGB")
                for _, data in render_pages(file_path, dpi=self._dpi)]

    def _load(self) -> tuple[Any, Any]:
        if self._loaded is None:
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel

            processor = TrOCRProcessor.from_pretrained(self._model_id)
            model = VisionEncoderDecoderModel.from_pretrained(self._model_id)
            if self._device:
                model = model.to(self._device)
            self._loaded = (processor, model)
        return self._loaded

    def _run(self, file_path: str) -> tuple[list[list[str]], list[dict[str, Any]]]:
        processor, model = self._load()
        pages: list[list[str]] = []
        boxes: list[dict[str, Any]] = []
        for page_no, img in enumerate(self._images(file_path), start=1):
            spans = split_lines(img)
            crops = [img.crop((0, top, img.width, bottom)) for top, bottom in spans]
            texts: list[str] = []
            for i in range(0, len(crops), self._batch):
                pixel_values = processor(images=crops[i:i + self._batch],
                                         return_tensors="pt").pixel_values
                if self._device:
                    pixel_values = pixel_values.to(self._device)
                ids = model.generate(pixel_values)
                texts += [t.strip() for t in processor.batch_decode(ids, skip_special_tokens=True)]
            pages.append([t for t in texts if t])
            boxes += [
                {"type": "Line", "bbox": [0, top, img.width, bottom], "page": page_no,
                 "text": text, "id": f"p{page_no}-l{n}",
                 "page_width": img.width, "page_height": img.height}
                for n, ((top, bottom), text) in enumerate(zip(spans, texts)) if text
            ]
        return pages, boxes
