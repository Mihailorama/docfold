"""docfold - Turn any document into structured data."""

__version__ = "0.7.0"

from docfold.engines.base import (
    BoundingBox,
    DocumentEngine,
    EngineCapabilities,
    EngineResult,
    OutputFormat,
)
from docfold.engines.router import BatchResult, EngineRouter, ProgressCallback

__all__ = [
    "BatchResult",
    "BoundingBox",
    "DocumentEngine",
    "EngineCapabilities",
    "EngineResult",
    "EngineRouter",
    "OutputFormat",
    "ProgressCallback",
]
