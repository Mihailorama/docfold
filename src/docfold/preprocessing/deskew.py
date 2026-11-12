"""Straighten scanned page images before OCR.

Skew is estimated with a projection profile: the image is rotated over a range
of small angles and the angle whose row sums vary most (text lines aligned
with rows) wins. Needs Pillow and NumPy (``pip install docfold[deskew]``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def estimate_skew(image: Any, max_angle: float = 10.0, step: float = 0.5) -> float:
    """Skew angle in degrees (counter-clockwise rotation that straightens *image*).

    *image* is a PIL image or a path. Coarse search in *step* increments, then a
    refinement around the best angle at a tenth of the step.
    """
    import numpy as np
    from PIL import Image

    img = Image.open(image) if isinstance(image, (str, Path)) else image
    gray = img.convert("L")
    gray.thumbnail((1200, 1200))
    ink = Image.fromarray((np.asarray(gray) < 128).astype("uint8") * 255)

    def score(angle: float) -> float:
        rows = np.asarray(ink.rotate(angle, expand=False, fillcolor=0), dtype=np.float32).sum(1)
        return float(np.var(rows))

    def best(lo: float, hi: float, st: float) -> float:
        n = int(round((hi - lo) / st)) + 1
        return max((lo + i * st for i in range(n)), key=score)

    coarse = best(-max_angle, max_angle, step)
    return round(best(coarse - step, coarse + step, step / 10), 2)


def deskew_image(
    src: str, dst: str | None = None, max_angle: float = 10.0, min_angle: float = 0.2,
) -> tuple[str, float]:
    """Write a straightened copy of the image at *src*; return ``(path, angle)``.

    Angles below *min_angle* are left alone (the source path is returned).
    *dst* defaults to ``<name>_deskewed<ext>`` next to the source.
    """
    from PIL import Image

    with Image.open(src) as img:
        angle = estimate_skew(img, max_angle=max_angle)
        if abs(angle) < min_angle:
            return src, angle
        fill = "white" if img.mode in ("RGB", "L") else None
        out = img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=fill)
        srcp = Path(src)
        path = Path(dst) if dst else srcp.with_name(f"{srcp.stem}_deskewed{srcp.suffix}")
        out.save(path)
    return str(path), angle
