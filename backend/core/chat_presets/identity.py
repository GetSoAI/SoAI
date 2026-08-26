"""SoAI - Chat preset identity canonicalization [backend/core/chat_presets/identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
import unicodedata

from core.chat_presets.constants import CHAT_PRESET_MAX_NAME_CODE_POINTS
from core.chat_presets.text_canonicalization import canonicalize_trimmed_text
from core.errors.exceptions import ValidationError
from core.types.json import JSONValue
from core.validation.integers import is_strict_int
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX

__all__ = (
    "canonicalize_chat_preset_name",
    "chat_preset_name_key",
    "require_chat_preset_id",
    "require_chat_preset_revision",
)

_PRESET_ID_PATTERN_TEXT = r"preset_[0-9a-f]{32}\Z"


def canonicalize_chat_preset_name(value: JSONValue) -> str:
    normalized = canonicalize_trimmed_text(
        value,
        field="Chat preset name",
        nullable=False,
    )
    if normalized is None:
        raise ValidationError("Chat preset name must be a non-empty string.")
    if len(normalized) > CHAT_PRESET_MAX_NAME_CODE_POINTS:
        raise ValidationError("Chat preset name must contain at most 255 Unicode code points.")
    return normalized


def chat_preset_name_key(name: str) -> str:
    canonical_name = canonicalize_chat_preset_name(name)
    return unicodedata.normalize("NFC", canonical_name).casefold()


def require_chat_preset_id(value: JSONValue) -> str:
    if not isinstance(value, str) or re.fullmatch(_PRESET_ID_PATTERN_TEXT, value) is None:
        raise ValidationError("Chat preset id is invalid.")
    return value


def require_chat_preset_revision(value: JSONValue) -> int:
    if not is_strict_int(value) or value < 1 or value > JAVASCRIPT_SAFE_INTEGER_MAX:
        raise ValidationError("Chat preset revision is invalid.")
    return value
