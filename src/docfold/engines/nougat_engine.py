"""Nougat engine adapter — Meta's academic document understanding model.

Install: ``pip install docfold[nougat]``

Nougat (Neural Optical Understanding for Academic Documents) is a transformer
model trained on arXiv papers.  It excels at converting academic PDFs —
including LaTeX formulas — into Markdown.

No API key needed; runs entirely locally.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf"}


class NougatEngine(DocumentEngine):
    """Adapter for Meta Nougat (academic PDF → Markdown).

    Best for scientific papers with heavy math notation.  Produces Mathpix-
    compatible Markdown with LaTeX equations.

    See https://github.com/facebookresearch/nougat
    """

    def __init__(
        self,
        model: str = "facebook/nougat-small",
        batch_size: int = 1,
        no_skipping: bool = False,
    ) -> None:
        self._model = model
        self._batch_size = batch_size
        self._no_skipping = no_skipping

    @property
    def name(self) -> str:
        return "nougat"

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
            import nougat  # noqa: F401
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
        content, page_count = await loop.run_in_executor(
            None, self._do_process, file_path, output_format
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            pages=page_count,
            processing_time_ms=elapsed_ms,
            metadata={"model": self._model},
        )

    def _do_process(
        self, file_path: str, output_format: OutputFormat
    ) -> tuple[str, int]:
        import torch
        from nougat import NougatModel
        from nougat.postprocessing import markdown_compatible
        from nougat.utils.dataset import LazyDataset
        from nougat.utils.device import move_to_device
        from torch.utils.data import DataLoader

        model = NougatModel.from_pretrained(self._model)
        model = move_to_device(model)
        model.eval()

        dataset = LazyDataset(
            file_path, None, None,
            model.encoder.prepare_input,
        )
        dataloader = DataLoader(
            dataset,
            batch_size=self._batch_size,
            shuffle=False,
        )

        pages_text: list[str] = []
        for idx, sample in enumerate(dataloader):
            sample = sample.to(model.device)

            if sample is None:
                pages_text.append("")
                continue

            with torch.no_grad():
                output = model.inference(
                    image_tensors=sample,
                    early_stopping=not self._no_skipping,
                )

            for page_text in output["predictions"]:
                page_text = markdown_compatible(page_text)
                pages_text.append(page_text)

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
