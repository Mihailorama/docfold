"""Optional utility building blocks for consumers who want smart routing."""

from docfold.utils.pre_analysis import FileAnalysis, pre_analyze
from docfold.utils.quality import QualityThresholds, quality_ok

__all__ = [
    "FileAnalysis",
    "QualityThresholds",
    "pre_analyze",
    "quality_ok",
]
