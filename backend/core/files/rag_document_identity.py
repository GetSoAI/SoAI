"""SoAI - RAG document filename and file-type identity [backend/core/files/rag_document_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.files.operations import secure_filename
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "NormalizedRAGDocumentIdentity",
    "normalize_rag_document_identity",
    "normalize_rag_file_type",
)


@dataclass(frozen=True, slots=True)
class NormalizedRAGDocumentIdentity:
    filename: str
    file_type: str


def normalize_rag_file_type(file_type: str) -> str:
    normalized = coerce_optional_trimmed_str(file_type)
    if normalized is None:
        raise ValidationError("RAG document file_type must be a non-empty string.")
    lowered = normalized.lower()
    if not _is_valid_file_type(lowered):
        raise ValidationError("RAG document file_type contains invalid characters.")
    return lowered


def normalize_rag_document_identity(
    filename: str,
    *,
    fallback_filename: str = "document",
    preserve_display_path: bool = False,
) -> NormalizedRAGDocumentIdentity:
    normalized_filename = coerce_optional_trimmed_str(filename)
    fallback = secure_filename(fallback_filename)
    if normalized_filename is None:
        normalized_filename = fallback or "document"
    if "\x00" in normalized_filename:
        raise ValidationError("RAG document filename contains invalid characters.")
    safe_basename = secure_filename(normalized_filename)
    file_type = _derive_file_type(normalized_filename, safe_basename)
    if preserve_display_path:
        display_filename = normalized_filename
    else:
        display_filename = safe_basename
    if not display_filename:
        display_filename = fallback or safe_basename or "document"
    return NormalizedRAGDocumentIdentity(filename=display_filename, file_type=file_type)


def _derive_file_type(raw_filename: str, safe_basename: str) -> str:
    raw_basename = os.path.basename(raw_filename.replace("\\", "/"))
    extension = os.path.splitext(raw_basename)[1]
    if not extension:
        extension = os.path.splitext(safe_basename)[1]
        if not safe_basename and not extension:
            return "txt"
        if not extension:
            return "txt"
    return normalize_rag_file_type(extension.lstrip("."))


def _is_valid_file_type(file_type: str) -> bool:
    if len(file_type) > 64 or not _is_ascii_lowercase_alphanumeric(file_type[0]):
        return False
    for character in file_type[1:]:
        if not _is_ascii_lowercase_alphanumeric(character) and character != "-":
            return False
    return True


def _is_ascii_lowercase_alphanumeric(character: str) -> bool:
    return "a" <= character <= "z" or "0" <= character <= "9"
