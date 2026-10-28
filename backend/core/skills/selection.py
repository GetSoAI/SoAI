"""SoAI - Skill selection identity and revision validation [backend/core/skills/selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from uuid import UUID

from core.errors.exceptions import ValidationError
from core.skills.limits import MAX_INSTALLED_SKILLS
from core.types.json import JSONValue
from core.validation.integers import is_strict_int
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX

__all__ = (
    "require_skill_id",
    "require_skill_upload_id",
    "require_skill_revision",
    "canonicalize_skill_selection",
)


def require_skill_id(value: JSONValue) -> str:
    if not isinstance(value, str) or re.fullmatch(r"skill_[0-9a-f]{32}", value) is None:
        raise ValidationError("Skill identity is invalid.")
    return value


def require_skill_upload_id(value: str) -> str:
    try:
        normalized = str(UUID(value))
    except ValueError as exception:
        raise ValidationError("Skill upload identity must be a UUID.") from exception
    if normalized != value:
        raise ValidationError("Skill upload identity must use canonical UUID formatting.")
    return normalized


def require_skill_revision(value: JSONValue) -> int:
    if not is_strict_int(value) or not 0 <= value <= JAVASCRIPT_SAFE_INTEGER_MAX:
        raise ValidationError("Skill selection revision is invalid.")
    return value


def canonicalize_skill_selection(value: JSONValue) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_INSTALLED_SKILLS:
        raise ValidationError(
            "Skill selection must be a bounded list of installed skill identities."
        )
    selected = tuple(require_skill_id(item) for item in value)
    if len(set(selected)) != len(selected):
        raise ValidationError("Skill selection must not contain duplicate identities.")
    return tuple(sorted(selected))
