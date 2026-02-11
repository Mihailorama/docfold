"""MinerU / PDF-Extract-Kit engine adapter.

Install: ``pip install docfold[mineru]``

Note: First run downloads model weights (~2-5 GB).
License: AGPL-3.0 — see https://github.com/opendatalab/MinerU
"""

from __future__ import annotations

import logging
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf"}


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
            None, self._run_mineru, file_path, output_format
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            processing_time_ms=elapsed_ms,
            metadata=metadata,
        )

    def _run_mineru(self, file_path: str, output_format: OutputFormat) -> tuple[str, dict]:
        """Synchronous MinerU processing.

        This is a placeholder implementation. The actual integration will
        depend on MinerU's Python API which may change across versions.
        Adapt the import paths and function calls to the installed version.
        """
        # TODO: Replace with actual MinerU API calls once version is pinned.
        # The general pattern is:
        #
        #   from magic_pdf.pipe.UNIPipe import UNIPipe
        #   from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
        #
        #   reader = DiskReaderWriter(parent_dir)
        #   pipe = UNIPipe(pdf_bytes, model_list, reader)
        #   pipe.pipe_classify()
        #   pipe.pipe_analyze()
        #   pipe.pipe_parse()
        #   md_content = pipe.pipe_mk_markdown(...)

        raise NotImplementedError(
            "MinerU adapter requires magic-pdf to be installed and configured. "
            "Install with: pip install docfold[mineru]"
        )
