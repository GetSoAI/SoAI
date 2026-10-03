"""SoAI - Software update record version validation [backend/core/tasks/software_update_versions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.strings import coerce_required_non_empty_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("require_software_update_version",)

VERSION_PATTERN = r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?\Z"


def require_software_update_version(value: JSONValue, *, field: str) -> str:
    version = coerce_required_non_empty_str(value, label=field)
    if re.fullmatch(VERSION_PATTERN, version) is None:
        raise ValidationError(f"{field} is invalid.")
    return version
