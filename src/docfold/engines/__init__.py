"""Document structuring engine adapters."""

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat
from docfold.engines.router import EngineRouter

__all__ = [
    "DocumentEngine",
    "EngineCapabilities",
    "EngineResult",
    "EngineRouter",
    "OutputFormat",
]
