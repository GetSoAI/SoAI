"""SoAI - Core filesystem path input types and coercion [backend/core/filesystem/path_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    type PathInput = str | os.PathLike[str]

__all__ = ("coerce_path",)


def coerce_path(value: PathInput) -> str:
    if isinstance(value, os.PathLike):
        value = os.fspath(value)
    if not isinstance(value, str):
        raise ValidationError("Path must be a string or os.PathLike instance.")
    if not value:
        raise ValidationError("Path cannot be empty.")
    normalized = value.strip()
    if not normalized:
        raise ValidationError("Path cannot be empty.")
    return value
