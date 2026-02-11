"""File type detection and metadata extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Extension → category mapping
_CATEGORY_MAP: dict[str, str] = {
    # Documents
    "pdf": "document",
    "docx": "document",
    "doc": "document",
    "odt": "document",
    "rtf": "document",
    # Presentations
    "pptx": "presentation",
    "ppt": "presentation",
    "odp": "presentation",
    # Spreadsheets
    "xlsx": "spreadsheet",
    "xls": "spreadsheet",
    "csv": "spreadsheet",
    "ods": "spreadsheet",
    # Images
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "tiff": "image",
    "tif": "image",
    "bmp": "image",
    "webp": "image",
    "gif": "image",
    # Web
    "html": "web",
    "htm": "web",
    # E-books
    "epub": "ebook",
    # Audio
    "wav": "audio",
    "mp3": "audio",
    "vtt": "audio",
}

_MIME_MAP: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tiff": "image/tiff",
    "html": "text/html",
    "csv": "text/csv",
}


@dataclass
class FileInfo:
    """Metadata about a file for engine selection."""

    path: str
    extension: str
    category: str
    mime_type: str | None

    @property
    def is_image(self) -> bool:
        return self.category == "image"

    @property
    def is_pdf(self) -> bool:
        return self.extension == "pdf"

    @property
    def is_office(self) -> bool:
        return self.category in {"document", "presentation", "spreadsheet"}


def detect_file_type(file_path: str) -> FileInfo:
    """Detect file type from extension and optionally from magic bytes."""
    ext = Path(file_path).suffix.lstrip(".").lower()
    category = _CATEGORY_MAP.get(ext, "unknown")
    mime = _MIME_MAP.get(ext)

    # Try filetype library for magic-byte detection if available
    if mime is None:
        try:
            import filetype

            kind = filetype.guess(file_path)
            if kind:
                mime = kind.mime
                if not ext:
                    ext = kind.extension or ""
                    category = _CATEGORY_MAP.get(ext, "unknown")
        except (ImportError, Exception):
            pass

    return FileInfo(
        path=file_path,
        extension=ext,
        category=category,
        mime_type=mime,
    )
