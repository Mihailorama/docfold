"""MinerU 2.x engine adapter.

Install: ``pip install docfold[mineru]``

Built on `MinerU <https://github.com/opendatalab/MinerU>`_ (the ``mineru``
package, formerly ``magic-pdf``). Uses the supported programmatic entry point
:func:`mineru.cli.common.do_parse`.

Note: First run downloads model weights (~1-3 GB).
License: AGPL-3.0 — see https://github.com/opendatalab/MinerU
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf"}

# Lazy-loaded at first use; patchable in tests.
do_parse: Any = None
read_fn: Any = None


def _ensure_imports() -> None:
    """Import the ``mineru`` programmatic API on first use."""
    global do_parse, read_fn
    if do_parse is not None:
        return
    from mineru.cli.common import do_parse as _do_parse
    from mineru.cli.common import read_fn as _read_fn

    do_parse = _do_parse
    read_fn = _read_fn


class MinerUEngine(DocumentEngine):
    """Adapter for MinerU 2.x, the end-to-end PDF structuring tool.

    See https://github.com/opendatalab/MinerU
    """

    def __init__(
        self,
        config_path: str | None = None,
        gpu: bool = False,
        backend: str = "pipeline",
        parse_method: str = "auto",
    ) -> None:
        self._config_path = config_path
        self._gpu = gpu
        self._backend = backend
        self._parse_method = parse_method

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
            import mineru  # noqa: F401
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

        backend = kwargs.get("backend", self._backend)
        parse_method = kwargs.get("parse_method", self._parse_method)
        lang = kwargs.get("lang") or "ch"
        start_page = kwargs.get("start_page")
        end_page = kwargs.get("end_page")
        want_json = output_format == OutputFormat.JSON

        pdf_bytes = read_fn(file_path)
        name = "document"

        with tempfile.TemporaryDirectory() as out_dir:
            do_parse(
                output_dir=out_dir,
                pdf_file_names=[name],
                pdf_bytes_list=[pdf_bytes],
                p_lang_list=[lang],
                backend=backend,
                parse_method=parse_method,
                start_page_id=start_page if start_page is not None else 0,
                end_page_id=end_page,
                f_dump_md=not want_json,
                f_dump_content_list=want_json,
                f_draw_layout_bbox=False,
                f_draw_span_bbox=False,
                f_dump_middle_json=False,
                f_dump_model_output=False,
                f_dump_orig_pdf=False,
            )

            md_dir = os.path.join(out_dir, name, self._output_subdir(backend, parse_method))
            if want_json:
                target = os.path.join(md_dir, f"{name}_content_list.json")
            else:
                target = os.path.join(md_dir, f"{name}.md")

            if not os.path.exists(target):
                raise RuntimeError(
                    f"MinerU did not produce expected output at {target!r}. "
                    f"Output dir contents: {self._list_dir(out_dir)}"
                )

            with open(target, encoding="utf-8") as f:
                content = f.read()

        metadata = {
            "backend": backend,
            "parse_method": parse_method,
            "lang": lang,
        }

        return content, metadata

    @staticmethod
    def _output_subdir(backend: str, parse_method: str) -> str:
        """Subdirectory ``do_parse`` writes into, per backend.

        Mirrors upstream ``mineru.cli.common.do_parse``: pipeline → the
        ``parse_method`` name (e.g. ``auto``); vlm family → ``vlm``;
        hybrid family → ``hybrid_<parse_method>``.
        """
        if backend.startswith("vlm"):
            return "vlm"
        if backend.startswith("hybrid"):
            return f"hybrid_{parse_method}"
        return parse_method

    @staticmethod
    def _list_dir(root: str) -> list[str]:
        found: list[str] = []
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                found.append(os.path.relpath(os.path.join(dirpath, fn), root))
        return found
