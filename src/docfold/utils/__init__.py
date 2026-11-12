"""Optional utility building blocks for consumers who want smart routing."""

from docfold.utils.pre_analysis import FileAnalysis, pre_analyze
from docfold.utils.quality import (
    QualityThresholds,
    base64_ratio,
    default_quality_gate,
    quality_ok,
    strip_base64_images,
)

__all__ = [
    "FileAnalysis",
    "QualityThresholds",
    "base64_ratio",
    "default_quality_gate",
    "pre_analyze",
    "quality_ok",
    "strip_base64_images",
]
