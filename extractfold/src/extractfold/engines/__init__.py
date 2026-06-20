"""Structured-data extraction engine adapters."""

from extractfold.engines.base import (
    ExtractionCapabilities,
    ExtractionEngine,
    ExtractionField,
    ExtractionResult,
    Schema,
    load_schema,
)
from extractfold.engines.lift_engine import LiftEngine
from extractfold.engines.router import BatchExtractionResult, ExtractionRouter

__all__ = [
    "BatchExtractionResult",
    "ExtractionCapabilities",
    "ExtractionEngine",
    "ExtractionField",
    "ExtractionResult",
    "ExtractionRouter",
    "LiftEngine",
    "Schema",
    "load_schema",
]
