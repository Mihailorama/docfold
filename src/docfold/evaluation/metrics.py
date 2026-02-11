"""Quality metrics for evaluating document structuring results.

All metric functions follow the convention:
- First argument: extracted/predicted value
- Second argument: ground truth / reference value
- Return: float score (higher = better for F1/accuracy, lower = better for error rates)
"""

from __future__ import annotations


def compute_cer(predicted: str, reference: str) -> float:
    """Character Error Rate — Levenshtein distance normalized by reference length.

    Returns 0.0 for a perfect match. Can exceed 1.0 if predicted is much longer.
    """
    if not reference:
        return 0.0 if not predicted else float(len(predicted))
    try:
        from jiwer import cer
        return cer(reference, predicted)
    except ImportError:
        return _levenshtein_ratio(predicted, reference, char_level=True)


def compute_wer(predicted: str, reference: str) -> float:
    """Word Error Rate — edit distance at word level normalized by reference word count.

    Returns 0.0 for a perfect match.
    """
    if not reference.strip():
        return 0.0 if not predicted.strip() else float(len(predicted.split()))
    try:
        from jiwer import wer
        return wer(reference, predicted)
    except ImportError:
        return _levenshtein_ratio(predicted, reference, char_level=False)


def compute_table_f1(
    predicted_tables: list[list[list[str]]],
    reference_tables: list[list[list[str]]],
) -> float:
    """Table detection and cell-level F1 score.

    Each table is represented as a list of rows, each row is a list of cell strings.
    Returns F1 in [0, 1].
    """
    if not reference_tables and not predicted_tables:
        return 1.0
    if not reference_tables or not predicted_tables:
        return 0.0

    # Flatten all cells from all tables for a simple cell-level comparison
    ref_cells = _flatten_tables(reference_tables)
    pred_cells = _flatten_tables(predicted_tables)

    ref_set = set(ref_cells)
    pred_set = set(pred_cells)

    if not ref_set and not pred_set:
        return 1.0

    tp = len(ref_set & pred_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    recall = tp / len(ref_set) if ref_set else 0.0

    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def compute_heading_f1(
    predicted_headings: list[str],
    reference_headings: list[str],
) -> float:
    """Heading detection F1 — normalized text comparison.

    Returns F1 in [0, 1].
    """
    if not reference_headings and not predicted_headings:
        return 1.0
    if not reference_headings or not predicted_headings:
        return 0.0

    ref_norm = {_normalize(h) for h in reference_headings}
    pred_norm = {_normalize(h) for h in predicted_headings}

    tp = len(ref_norm & pred_norm)
    precision = tp / len(pred_norm) if pred_norm else 0.0
    recall = tp / len(ref_norm) if ref_norm else 0.0

    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def compute_reading_order_score(
    predicted_order: list[str],
    reference_order: list[str],
) -> float:
    """Reading order quality — Kendall's tau correlation.

    Returns a value in [-1, 1] where 1.0 = perfect order match.
    Only considers elements present in both lists.
    """
    common = [e for e in reference_order if e in predicted_order]
    if len(common) < 2:
        return 1.0 if len(common) == len(reference_order) else 0.0

    pred_indices = {e: i for i, e in enumerate(predicted_order)}
    pred_ranks = [pred_indices[e] for e in common]
    ref_ranks = list(range(len(common)))

    try:
        from scipy.stats import kendalltau
        tau, _ = kendalltau(ref_ranks, pred_ranks)
        return float(tau) if tau == tau else 0.0  # handle NaN
    except ImportError:
        # Simple concordance-based approximation
        n = len(common)
        concordant = 0
        total = 0
        for i in range(n):
            for j in range(i + 1, n):
                total += 1
                if (pred_ranks[i] - pred_ranks[j]) * (ref_ranks[i] - ref_ranks[j]) > 0:
                    concordant += 1
        return (2 * concordant - total) / total if total > 0 else 1.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, strip whitespace, collapse spaces."""
    return " ".join(text.lower().split())


def _flatten_tables(tables: list[list[list[str]]]) -> list[str]:
    """Flatten list-of-tables into a list of normalized cell strings."""
    cells = []
    for table in tables:
        for row in table:
            for cell in row:
                cells.append(_normalize(cell))
    return cells


def _levenshtein_ratio(predicted: str, reference: str, char_level: bool) -> float:
    """Pure-Python Levenshtein-based error rate (fallback when jiwer is not installed)."""
    if char_level:
        a, b = list(predicted), list(reference)
    else:
        a, b = predicted.split(), reference.split()

    if not b:
        return 0.0 if not a else float(len(a))

    n, m = len(a), len(b)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            temp = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
            prev = temp

    return dp[m] / m
