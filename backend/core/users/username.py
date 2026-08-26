"""SoAI - Canonical WebUI username contract [backend/core/users/username.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.errors.exceptions import ValidationError

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
USERNAME_PATTERN_TEXT = r"[A-Za-z0-9_.-]{3,50}\Z"


def require_canonical_username(value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError("Username must be a string.")
    if re.fullmatch(USERNAME_PATTERN_TEXT, value, re.ASCII) is None:
        raise ValidationError(
            "Username must be 3-50 ASCII letters, numbers, dots, underscores, or hyphens."
        )
    return value.lower()


__all__ = (
    "USERNAME_MAX_LENGTH",
    "USERNAME_MIN_LENGTH",
    "USERNAME_PATTERN_TEXT",
    "require_canonical_username",
)
