"""docfold - Turn any document into structured data."""

__version__ = "0.6.0"

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat
from docfold.engines.router import BatchResult, EngineRouter, ProgressCallback

__all__ = [
    "BatchResult",
    "DocumentEngine",
    "EngineResult",
    "EngineRouter",
    "OutputFormat",
    "ProgressCallback",
]
