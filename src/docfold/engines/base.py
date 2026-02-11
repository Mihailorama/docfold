"""Base interface for document structuring engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OutputFormat(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    TEXT = "text"


@dataclass
class EngineResult:
    """Unified result returned by all structuring engines.

    Every engine adapter must produce this dataclass so that callers
    never depend on engine-specific output shapes.
    """

    content: str
    """Primary output string (markdown, html, plain text, or json string)."""

    format: OutputFormat
    """Format of ``content``."""

    engine_name: str
    """Identifier of the engine that produced this result."""

    # --- optional enrichments ---

    metadata: dict[str, Any] = field(default_factory=dict)
    """Engine-specific metadata (model versions, config used, etc.)."""

    pages: int | None = None
    """Number of pages processed (if applicable)."""

    images: dict[str, str] | None = None
    """Extracted images as ``{filename: base64_data}``."""

    tables: list[dict[str, Any]] | None = None
    """Extracted tables as list of row-dicts."""

    bounding_boxes: list[dict[str, Any]] | None = None
    """Layout element bounding boxes ``[{type, bbox, page, ...}]``."""

    confidence: float | None = None
    """Overall confidence score in [0, 1] (if the engine provides one)."""

    processing_time_ms: int = 0
    """Wall-clock processing time in milliseconds."""


class DocumentEngine(ABC):
    """Abstract base class that every engine adapter must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique, lowercase engine identifier (e.g. ``'docling'``)."""
        ...

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """File extensions this engine can handle, without dots (e.g. ``{'pdf', 'docx'}``)."""
        ...

    @abstractmethod
    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        """Process a document and return a unified :class:`EngineResult`."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` if the engine's dependencies are installed and ready."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} available={self.is_available()}>"
