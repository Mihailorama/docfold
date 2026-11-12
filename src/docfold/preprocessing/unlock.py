"""Remove PDF protection before parsing.

Owner-password PDFs (copy/print restrictions) open fine but some engines
refuse them; user-password PDFs need the password. ``unlock_pdf`` tries the
``qpdf`` CLI first, then PyMuPDF.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def is_protected(file_path: str) -> bool:
    """``True`` when the PDF is encrypted or needs a password (needs PyMuPDF)."""
    import pymupdf

    with pymupdf.open(file_path) as doc:
        # Owner-password-only files open without a password, so is_encrypted is
        # False after open; the encryption method in the metadata still shows it.
        return bool(doc.needs_pass or doc.is_encrypted or (doc.metadata or {}).get("encryption"))


def unlock_pdf(file_path: str, out_path: str | None = None, password: str = "") -> str:
    """Return a path to an unprotected copy of *file_path*.

    Unprotected files are returned as is. Otherwise the decrypted copy goes to
    *out_path* (default ``<name>_unlocked.pdf`` next to the file), via
    ``qpdf --decrypt`` when installed, else PyMuPDF. *password* is the user
    password, if any (empty works for owner-password-only files).

    Raises:
        ValueError: the password is wrong or required.
        RuntimeError: neither qpdf nor PyMuPDF could write the copy.
    """
    if not is_protected(file_path):
        return file_path
    src = Path(file_path)
    dst = Path(out_path) if out_path else src.with_name(f"{src.stem}_unlocked.pdf")
    qpdf = shutil.which("qpdf")
    if qpdf:
        cmd = [qpdf, "--decrypt"]
        if password:
            cmd.append(f"--password={password}")
        try:
            run = subprocess.run([*cmd, str(src), str(dst)], capture_output=True, timeout=60)
            # qpdf exit 3 = success with warnings
            if run.returncode in (0, 3) and dst.is_file():
                return str(dst)
            logger.debug("qpdf failed: %s", run.stderr[:200])
        except (subprocess.SubprocessError, OSError) as exc:
            logger.debug("qpdf failed: %s", exc)
    import pymupdf

    with pymupdf.open(file_path) as doc:
        if doc.needs_pass and not doc.authenticate(password):
            raise ValueError("PDF needs a password" if not password else "wrong PDF password")
        try:
            doc.save(str(dst), encryption=getattr(pymupdf, "PDF_ENCRYPT_NONE", 1))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"could not write unlocked PDF: {exc}") from exc
    return str(dst)
