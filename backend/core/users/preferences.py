"""SoAI - Strict V1 user preference domain [backend/core/users/preferences.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.merge import deep_merge
from core.errors.exceptions import StateError, ValidationError
from core.media.tesseract_languages import require_ocr_language
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import MAX_JSON_NESTING_DEPTH, parse_json_value
from core.types.json import JSONDict, JSONValue, is_json_value
from core.types.json_value import copy_json_dict

__all__ = (
    "assert_supported_user_preferences",
    "decode_stored_user_preferences",
    "merge_user_preference_values",
    "serialize_user_preferences",
)

_ALLOWED_USER_PREFERENCES_TOP_LEVEL_KEYS = frozenset(
    {
        "ui",
        "chat",
        "logs",
        "terminal",
        "search",
        "hardware",
        "filters",
        "wizard",
        "settings",
        "misc",
    },
)


def assert_supported_user_preferences(preferences: JSONDict) -> None:
    if any(
        not isinstance(key, str) or not is_json_value(value) for key, value in preferences.items()
    ):
        raise ValidationError("User preferences must be JSON-compatible.")
    settings = preferences.get("settings")
    if isinstance(settings, dict) and "ocr_language" in settings:
        require_ocr_language(settings["ocr_language"])
    for key in preferences:
        if key not in _ALLOWED_USER_PREFERENCES_TOP_LEVEL_KEYS:
            raise ValidationError("Unsupported user preferences payload key set.")


def decode_stored_user_preferences(raw_preferences: JSONValue | bytes) -> JSONDict:
    if raw_preferences is None:
        return {}
    if not isinstance(raw_preferences, str | bytes):
        raise StateError("Stored user preferences have an invalid type.")
    try:
        parsed = parse_json_value(
            raw_preferences,
            field="stored user preferences",
            max_depth=MAX_JSON_NESTING_DEPTH,
            strict_utf8=True,
            reject_duplicate_keys=True,
        )
    except ValidationError as exception:
        raise StateError("Stored user preferences are invalid JSON.") from exception
    if not isinstance(parsed, dict):
        raise StateError("Stored user preferences must be a JSON object.")
    try:
        assert_supported_user_preferences(parsed)
    except ValidationError as exception:
        raise StateError("Stored user preferences contain unsupported data.") from exception
    return copy_json_dict(parsed)


def serialize_user_preferences(preferences: JSONDict) -> str:
    assert_supported_user_preferences(preferences)
    try:
        serialized = serialize_json_compact_stable_strict(preferences)
        parse_json_value(
            serialized,
            field="user preferences",
            max_depth=MAX_JSON_NESTING_DEPTH,
            reject_duplicate_keys=True,
        )
    except (TypeError, ValueError, ValidationError) as exception:
        raise ValidationError("User preferences cannot be serialized safely.") from exception
    return serialized


def merge_user_preference_values(current: JSONDict, patch: JSONDict) -> JSONDict:
    assert_supported_user_preferences(current)
    assert_supported_user_preferences(patch)
    merged = copy_json_dict(current)
    deep_merge(merged, copy_json_dict(patch), expand_dots=False)
    assert_supported_user_preferences(merged)
    return merged
