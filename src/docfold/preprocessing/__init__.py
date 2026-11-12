"""File preprocessing utilities — format detection, temp file management, normalization."""

from docfold.preprocessing.detector import FileInfo, detect_file_type
from docfold.preprocessing.unlock import is_protected, unlock_pdf

__all__ = ["detect_file_type", "FileInfo", "is_protected", "unlock_pdf"]
