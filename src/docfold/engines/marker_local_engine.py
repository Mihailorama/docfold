"""Marker local engine adapter — high-quality PDF conversion running locally.

Install: ``pip install docfold[marker-local]`` (which installs ``marker-pdf``)

No API key needed; runs entirely locally using Surya-based models.
See https://github.com/VikParuchuri/marker
"""

from __future__ import annotations

import logging
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    "pdf", "docx", "pptx", "xlsx", "html", "epub",
    "png", "jpg", "jpeg", "webp", "gif", "tiff",
}

# Lazy-loaded; patchable in tests.
PdfConverter: Any = None
create_model_dict: Any = None
text_from_rendered: Any = None


def _ensure_imports() -> None:
    """Import marker dependencies on first use."""
    global PdfConverter, create_model_dict, text_from_rendered
    if PdfConverter is not None:
        return
    from marker.converters.pdf import PdfConverter as _PdfConverter  # noqa: N814
    from marker.models import create_model_dict as _cmd
    from marker.output import text_from_rendered as _tfr
    PdfConverter = _PdfConverter
    create_model_dict = _cmd
    text_from_rendered = _tfr


class MarkerLocalEngine(DocumentEngine):
    """Adapter for Marker running locally (no API key).

    Uses the open-source ``marker-pdf`` library with Surya-based models
    for layout detection, OCR, and document conversion.

    See https://github.com/VikParuchuri/marker
    """

    def __init__(
        self,
        *,
        force_ocr: bool = False,
        **kwargs: Any,
    ) -> None:
        self._force_ocr = force_ocr
        self._kwargs = kwargs
        self._converter: Any = None

    @property
    def name(self) -> str:
        return "marker_local"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            table_structure=True,
            heading_detection=True,
        )

    def is_available(self) -> bool:
        try:
            import marker  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_converter(self) -> Any:
        """Lazy-init the converter (loads models on first call)."""
        if self._converter is None:
            _ensure_imports()
            config = {}
            if self._force_ocr:
                config["force_ocr"] = True
            config.update(self._kwargs)
            artifact_dict = create_model_dict()
            self._converter = PdfConverter(artifact_dict=artifact_dict, config=config)
        return self._converter

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        import asyncio

        start = time.perf_counter()

        loop = asyncio.get_running_loop()
        content, metadata = await loop.run_in_executor(
            None, self._run_marker, file_path, output_format,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            processing_time_ms=elapsed_ms,
            pages=metadata.get("pages"),
            metadata=metadata,
        )

    def _run_marker(
        self, file_path: str, output_format: OutputFormat,
    ) -> tuple[str, dict]:
        _ensure_imports()
        converter = self._get_converter()

        rendered = converter(file_path)
        text, _, images = text_from_rendered(rendered)

        if output_format == OutputFormat.JSON:
            import json
            content = json.dumps(
                {"markdown": text, "images": list(images.keys()) if images else []},
                ensure_ascii=False,
            )
        elif output_format == OutputFormat.HTML:
            # Simple markdown-to-html wrapping
            content = f"<html><body><pre>{text}</pre></body></html>"
        else:
            content = text

        metadata = {
            "method": "marker_local",
            "image_count": len(images) if images else 0,
        }

        return content, metadata
