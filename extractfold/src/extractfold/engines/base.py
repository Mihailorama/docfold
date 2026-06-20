"""Base interface for structured-data extraction engines.

Where ``docfold`` turns a document into a *representation* (Markdown / HTML /
text), ``extractfold`` turns a document **plus a JSON Schema** into a
*schema-conformant dict*.  The contract is therefore different:

- **Input:** a document *and* a target schema.
- **Output:** :class:`ExtractionResult` whose ``data`` conforms to the schema.
- **Enrichments:** per-field confidence and per-field provenance (page + bbox),
  rather than reading order / table structure.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# A schema may be supplied as a parsed dict, a path to a ``.json`` file, a raw
# JSON string, or the name of a schema saved in an engine's local library.
Schema = dict[str, Any] | str


def load_schema(schema: Schema) -> dict[str, Any]:
    """Normalize a :data:`Schema` into a plain ``dict``.

    Accepts an already-parsed dict, a path to a ``.json`` file, or a raw JSON
    string.  A bare name (no ``{`` and not an existing file) is returned as a
    ``{"$ref": name}`` marker so engines with a saved-schema library can
    resolve it themselves.
    """
    if isinstance(schema, dict):
        return schema
    if not isinstance(schema, str):
        raise TypeError(f"schema must be a dict or str, got {type(schema).__name__}")

    text = schema.strip()
    if text.startswith("{"):
        return json.loads(text)

    path = Path(schema)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    # Treat as a named schema reference; engines may resolve it from a library.
    return {"$ref": schema}


@dataclass(frozen=True)
class ExtractionCapabilities:
    """Declares what enrichments an engine can populate in an :class:`ExtractionResult`."""

    field_confidence: bool = False
    """Engine reports a per-field confidence score."""

    provenance: bool = False
    """Engine reports per-field source location (page and/or bbox)."""

    nested_schemas: bool = False
    """Engine supports nested objects and arrays in the schema."""

    batch: bool = False
    """Engine can extract from many documents in a single inference call."""

    local: bool = False
    """Engine can run fully on local hardware (no network call)."""

    remote: bool = False
    """Engine calls a hosted/remote API."""


@dataclass
class ExtractionField:
    """A single extracted field with optional confidence and provenance."""

    value: Any
    confidence: float | None = None
    page: int | None = None
    """1-based page number the value was sourced from (if known)."""
    bbox: list[float] | None = None
    """Source bounding box ``[x0, y0, x1, y1]`` (if known)."""
    source_text: str | None = None
    """Verbatim span the value was derived from (if known)."""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"value": self.value}
        if self.confidence is not None:
            d["confidence"] = self.confidence
        if self.page is not None:
            d["page"] = self.page
        if self.bbox is not None:
            d["bbox"] = self.bbox
        if self.source_text is not None:
            d["source_text"] = self.source_text
        return d


@dataclass
class ExtractionResult:
    """Unified result returned by every extraction engine."""

    data: dict[str, Any]
    """The extracted data, conforming to the supplied schema."""

    engine_name: str
    """Identifier of the engine that produced this result."""

    schema: dict[str, Any] | None = None
    """The JSON Schema used for this extraction (normalized)."""

    field_confidence: dict[str, float] | None = None
    """Per-field confidence scores keyed by (dotted) field path."""

    provenance: dict[str, ExtractionField] | None = None
    """Per-field provenance keyed by (dotted) field path."""

    valid: bool | None = None
    """Whether ``data`` validated against ``schema`` (``None`` if not checked)."""

    raw: str | None = None
    """Raw model output before parsing (when available)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Engine-specific metadata (model version, token count, errors, etc.)."""

    pages: int | None = None
    """Number of pages processed (if applicable)."""

    processing_time_ms: int = 0
    """Wall-clock processing time in milliseconds."""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "data": self.data,
            "engine_name": self.engine_name,
            "valid": self.valid,
            "pages": self.pages,
            "processing_time_ms": self.processing_time_ms,
            "metadata": self.metadata,
        }
        if self.field_confidence is not None:
            d["field_confidence"] = self.field_confidence
        if self.provenance is not None:
            d["provenance"] = {k: v.to_dict() for k, v in self.provenance.items()}
        return d


class ExtractionEngine(ABC):
    """Abstract base class that every extraction-engine adapter must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique, lowercase engine identifier (e.g. ``'lift'``)."""
        ...

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """File extensions this engine can handle, without dots (e.g. ``{'pdf', 'png'}``)."""
        ...

    @abstractmethod
    async def extract(
        self,
        file_path: str,
        schema: Schema,
        **kwargs: Any,
    ) -> ExtractionResult:
        """Extract schema-conformant data from *file_path*."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` if the engine's dependencies are installed and ready."""
        ...

    @property
    def capabilities(self) -> ExtractionCapabilities:
        """Declare what enrichments this engine populates.  Defaults to all ``False``."""
        return ExtractionCapabilities()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} available={self.is_available()}>"
