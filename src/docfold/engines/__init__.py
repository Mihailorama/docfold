"""Document structuring engine adapters."""

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat
from docfold.engines.router import EngineRouter

__all__ = [
    "DocumentEngine",
    "EngineResult",
    "EngineRouter",
    "OutputFormat",
]
