"""Self-update helpers — ``docfold update``.

Keeps installs current without users tracking PyPI: ``--check`` compares the
installed version against the latest release, the default action upgrades in
place via the running interpreter's pip. Pure helpers live here so they are
unit-testable offline; the argparse wiring lives in :mod:`docfold.cli`.

Stdlib-only (urllib) — docfold's core stays dependency-free.
"""

from __future__ import annotations

import json
import re
import sys
from urllib.request import urlopen

PYPI_JSON_URL = "https://pypi.org/pypi/docfold/json"


def latest_version(timeout: float = 10.0) -> str:
    """Return the latest docfold version published on PyPI."""
    with urlopen(PYPI_JSON_URL, timeout=timeout) as response:
        payload = json.load(response)
    return str(payload["info"]["version"])


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version)[:3])


def is_newer(latest: str, current: str) -> bool:
    """True when *latest* is strictly newer than *current* (numeric compare)."""
    return _version_tuple(latest) > _version_tuple(current)


def build_update_argv(extras: str | None = None) -> list[str]:
    """pip command that upgrades docfold in the running interpreter.

    ``extras`` is a comma-separated list (e.g. ``"mcp,docling"``) baked
    into the requirement as ``docfold[mcp,docling]``.
    """
    target = "docfold"
    if extras:
        cleaned = ",".join(e.strip() for e in extras.split(",") if e.strip())
        if cleaned:
            target = f"docfold[{cleaned}]"
    return [sys.executable, "-m", "pip", "install", "--upgrade", target]
