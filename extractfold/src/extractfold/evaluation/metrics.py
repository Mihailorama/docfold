"""Extraction-quality metrics.

These differ from docfold's text metrics (WER/CER, reading order, table TEDS):
extraction is judged on whether the right *fields* got the right *values* and
whether the output conforms to the schema.
"""

from __future__ import annotations

from typing import Any


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dict/list into dotted-path → scalar pairs."""
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def _normalize(value: Any) -> Any:
    """Light normalization so ``"1,000"`` ≈ ``"1000"`` and case/space differ less."""
    if isinstance(value, str):
        return value.strip().casefold().replace(",", "")
    return value


def field_accuracy(
    predicted: dict[str, Any],
    gold: dict[str, Any],
    normalize: bool = True,
) -> dict[str, Any]:
    """Compare ``predicted`` against ``gold`` field-by-field.

    Returns a report with overall ``accuracy`` plus the matched / mismatched /
    missing / extra field paths, computed over the flattened leaf values.
    """
    p = _flatten(predicted)
    g = _flatten(gold)

    matched: list[str] = []
    mismatched: list[str] = []
    missing: list[str] = []

    for key, gold_val in g.items():
        if key not in p:
            missing.append(key)
            continue
        pv, gv = p[key], gold_val
        if normalize:
            pv, gv = _normalize(pv), _normalize(gv)
        (matched if pv == gv else mismatched).append(key)

    extra = [k for k in p if k not in g]
    accuracy = len(matched) / len(g) if g else 1.0

    return {
        "accuracy": accuracy,
        "matched": matched,
        "mismatched": mismatched,
        "missing": missing,
        "extra": extra,
        "total_gold_fields": len(g),
    }


def schema_compliance(data: dict[str, Any], schema: dict[str, Any]) -> bool:
    """Return ``True`` if ``data`` validates against ``schema``.

    Uses ``jsonschema`` when installed (``extractfold[evaluation]``); otherwise
    raises a helpful error.
    """
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - exercised only without dep
        raise RuntimeError(
            "schema_compliance requires jsonschema. "
            "Install with `pip install extractfold[evaluation]`."
        ) from exc

    try:
        jsonschema.validate(instance=data, schema=schema)
        return True
    except jsonschema.ValidationError:
        return False
