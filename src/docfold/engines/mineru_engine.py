"""MinerU / PDF-Extract-Kit engine adapter.

Install: ``pip install docfold[mineru]``

Note: First run downloads model weights (~2-5 GB).
License: AGPL-3.0 — see https://github.com/opendatalab/MinerU
"""

from __future__ import annotations

import logging
import tempfile
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf"}

# Lazy-loaded at first use; patchable in tests.
PymuDocDataset: Any = None
SupportedPdfParseMethod: Any = None
FileBasedDataWriter: Any = None
doc_analyze: Any = None
convert_pdf_bytes_to_bytes_by_pymupdf: Any = None


def _ensure_imports() -> None:
    """Import magic_pdf dependencies on first use."""
    global PymuDocDataset, SupportedPdfParseMethod, FileBasedDataWriter
    global doc_analyze, convert_pdf_bytes_to_bytes_by_pymupdf
    if PymuDocDataset is not None:
        return
    from magic_pdf.config.enums import SupportedPdfParseMethod as _SPM  # noqa: N814
    from magic_pdf.data.data_reader_writer import FileBasedDataWriter as _FBDW  # noqa: N814
    from magic_pdf.data.dataset import PymuDocDataset as _PDD  # noqa: N814
    try:
        from magic_pdf.libs.pdf_utils import (
            convert_pdf_bytes_to_bytes_by_pymupdf as _convert,
        )
    except (ImportError, ModuleNotFoundError):
        from magic_pdf.tools.common import (
            convert_pdf_bytes_to_bytes_by_pymupdf as _convert,
        )

    # doc_analyze location varies across magic-pdf versions.
    try:
        from magic_pdf.operators.models import doc_analyze as _da
    except ImportError:
        from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze as _da

    PymuDocDataset = _PDD
    SupportedPdfParseMethod = _SPM
    FileBasedDataWriter = _FBDW
    doc_analyze = _da
    convert_pdf_bytes_to_bytes_by_pymupdf = _convert


class MinerUEngine(DocumentEngine):
    """Adapter for MinerU (magic-pdf), the end-to-end PDF structuring tool
    built on PDF-Extract-Kit.

    See https://github.com/opendatalab/MinerU
    """

    def __init__(self, config_path: str | None = None, gpu: bool = False) -> None:
        self._config_path = config_path
        self._gpu = gpu

    @property
    def name(self) -> str:
        return "mineru"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            table_structure=True, heading_detection=True, reading_order=True,
        )

    def is_available(self) -> bool:
        try:
            import magic_pdf  # noqa: F401
            return True
        except ImportError:
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
        content, metadata = await loop.run_in_executor(
            None, self._run_mineru, file_path, output_format, kwargs
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

    def _run_mineru(
        self, file_path: str, output_format: OutputFormat, kwargs: dict[str, Any],
    ) -> tuple[str, dict]:
        _ensure_imports()

        # PyTorch 2.6+ defaults weights_only=True which breaks loading
        # doclayout_yolo model weights containing custom classes.
        try:
            import doclayout_yolo.nn.tasks as _tasks
            import torch
            _safe_classes = [
                cls for cls in vars(_tasks).values()
                if isinstance(cls, type)
            ]
            # The YOLO checkpoint also requires dill._dill._load_type
            try:
                from dill._dill import _load_type
                _safe_classes.append(_load_type)
            except ImportError:
                pass
            if _safe_classes:
                torch.serialization.add_safe_globals(_safe_classes)
        except Exception:
            pass

        start_page = kwargs.get("start_page")
        end_page = kwargs.get("end_page")
        lang = kwargs.get("lang")

        with open(file_path, "rb") as f:
            pdf_bytes = f.read()

        if start_page is not None or end_page is not None:
            pdf_bytes = convert_pdf_bytes_to_bytes_by_pymupdf(
                pdf_bytes,
                start_page or 0,
                end_page,
            )

        ds = PymuDocDataset(pdf_bytes, lang=lang)
        classify_result = ds.classify()
        is_text_pdf = classify_result == SupportedPdfParseMethod.TXT

        with tempfile.TemporaryDirectory() as tmp_dir:
            image_writer = FileBasedDataWriter(tmp_dir)

            infer_result = ds.apply(
                doc_analyze,
                ocr=not is_text_pdf,
                lang=lang,
            )

            if is_text_pdf:
                pipe_result = infer_result.pipe_txt_mode(
                    image_writer, debug_mode=False, lang=lang,
                )
            else:
                pipe_result = infer_result.pipe_ocr_mode(
                    image_writer, debug_mode=False, lang=lang,
                )

            if output_format == OutputFormat.JSON:
                content = pipe_result.get_content_list(tmp_dir)
            else:
                content = pipe_result.get_markdown(tmp_dir)

        metadata = {
            "method": "txt" if is_text_pdf else "ocr",
        }

        return content, metadata
