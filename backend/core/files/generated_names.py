"""SoAI - Bounded generated storage names and upload suffixes [backend/core/files/generated_names.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import ValidationError
from core.filesystem.component_limits import filesystem_component_limit

__all__ = ("generated_upload_filename", "normalize_upload_suffix")


def normalize_upload_suffix(filename: str) -> str:
    extension = os.path.splitext(filename)[1].lower()
    value = extension[1:]
    if not value or len(value) > 16 or not value.isalnum():
        return ""
    return extension


def generated_upload_filename(file_id: str, safe_filename: str, directory: str) -> str:
    prefix = f"{file_id}_"
    budget = filesystem_component_limit(directory) - len(prefix)
    if budget < 1 or not safe_filename.isascii() or not file_id.isascii():
        raise ValidationError("Generated upload name cannot fit the destination filesystem.")
    if len(safe_filename) <= budget:
        return prefix + safe_filename
    suffix = normalize_upload_suffix(safe_filename)
    stem_budget = budget - len(suffix)
    if stem_budget < 1:
        raise ValidationError("Generated upload name cannot preserve its extension.")
    original_suffix = os.path.splitext(safe_filename)[1]
    stem = safe_filename[: -len(original_suffix)] if suffix else safe_filename
    preserved_suffix = original_suffix if suffix else ""
    return prefix + stem[:stem_budget] + preserved_suffix
