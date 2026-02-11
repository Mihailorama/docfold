"""Evaluation framework for comparing document structuring engines."""

from docfold.evaluation.metrics import (
    compute_cer,
    compute_heading_f1,
    compute_reading_order_score,
    compute_table_f1,
    compute_wer,
)

__all__ = [
    "compute_cer",
    "compute_wer",
    "compute_table_f1",
    "compute_heading_f1",
    "compute_reading_order_score",
]
