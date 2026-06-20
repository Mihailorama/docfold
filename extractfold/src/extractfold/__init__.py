"""extractfold — turn any document into schema-conformant structured data.

A unified Python interface over structured-data extraction engines (Lift first;
NuExtract, LLM structured outputs, and LlamaExtract to follow), with built-in
evaluation.  Sibling project to ``docfold`` (document → Markdown/layout).
"""

from extractfold.engines import (
    BatchExtractionResult,
    ExtractionCapabilities,
    ExtractionEngine,
    ExtractionField,
    ExtractionResult,
    ExtractionRouter,
    LiftEngine,
    Schema,
    load_schema,
)

__version__ = "0.1.0"

__all__ = [
    "BatchExtractionResult",
    "ExtractionCapabilities",
    "ExtractionEngine",
    "ExtractionField",
    "ExtractionResult",
    "ExtractionRouter",
    "LiftEngine",
    "Schema",
    "__version__",
    "load_schema",
]
