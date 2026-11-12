"""Base interface for document structuring engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class EngineCapabilities:
    """Declares what enrichments an engine can populate in EngineResult."""

    bounding_boxes: bool = False
    confidence: bool = False
    images: bool = False
    table_structure: bool = False
    heading_detection: bool = False
    reading_order: bool = False


class OutputFormat(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    TEXT = "text"


@dataclass
class BoundingBox:
    """Unified bounding box for a layout element.

    All engines must produce bounding boxes in this format.  Fields that
    an engine cannot populate should be left at their defaults.

    Detailization varies by engine:
    - **pymupdf** — block-level boxes (Text / Image), no polygon.
    - **marker** — block-level with rich types (SectionHeader, Table, …),
      polygon coordinates, and per-block confidence.
    - **docling** / cloud engines — may include reading order and table cells.
    """

    type: str
    """Block type: ``Text``, ``Image``, ``Table``, ``SectionHeader``, etc."""

    bbox: list[float]
    """Bounding rectangle as ``[x0, y0, x1, y1]`` in PDF points."""

    page: int
    """1-based page number (for display/labels)."""

    text: str = ""
    """Text content of the block (empty for images)."""

    id: str = ""
    """Unique identifier within the document (e.g. ``p1-b0``)."""

    polygon: list[list[float]] | None = None
    """Precise polygon outline ``[[x,y], ...]`` (when available)."""

    confidence: float | None = None
    """Per-block confidence score in ``[0, 1]`` (when available)."""

    page_width: float | None = None
    """Page width in PDF points (needed for coordinate normalization)."""

    page_height: float | None = None
    """Page height in PDF points (needed for coordinate normalization)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict, omitting None optional fields."""
        d: dict[str, Any] = {
            "type": self.type,
            "bbox": self.bbox,
            "page": self.page,
            "page_index": self.page - 1,
            "text": self.text,
            "id": self.id,
        }
        if self.polygon is not None:
            d["polygon"] = self.polygon
        if self.confidence is not None:
            d["confidence"] = self.confidence
        if self.page_width is not None:
            d["page_width"] = self.page_width
        if self.page_height is not None:
            d["page_height"] = self.page_height
        return d


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
    """Layout element bounding boxes — list of :class:`BoundingBox`-shaped dicts.

    Each dict must contain at least ``type``, ``bbox``, and ``page``.
    Use :meth:`BoundingBox.to_dict` to produce conformant entries.
    """

    confidence: float | None = None
    """Overall confidence score in [0, 1] (if the engine provides one)."""

    processing_time_ms: int = 0
    """Wall-clock processing time in milliseconds."""

    fallback_chain: list[dict[str, Any]] | None = None
    """Every engine attempt made by :meth:`EngineRouter.process`, in order.

    Each entry has ``engine``, ``chars`` (text length without inline base64
    images), ``confidence``, ``processing_time_ms``, ``selected`` and ``role``
    (``primary`` / ``fallback`` / ``bbox_supplement``), plus ``skip_reason``
    (quality gate or ``engine_unavailable``) or ``error`` when it applies.
    ``None`` when the engine was called directly.
    """


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

    @property
    def capabilities(self) -> EngineCapabilities:
        """Declare what enrichments this engine populates in :class:`EngineResult`.

        Engines should override this to advertise their capabilities.
        Defaults to all ``False``.
        """
        return EngineCapabilities()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} available={self.is_available()}>"
