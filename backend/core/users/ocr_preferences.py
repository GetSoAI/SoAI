"""SoAI - Per-attempt committed OCR preference resolution [backend/core/users/ocr_preferences.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import NotFoundError, StateError
from core.media.tesseract_languages import DEFAULT_OCR_LANGUAGE, require_ocr_language
from core.types.json import JSONDict
from core.users.protocols_database import DatabaseUsersProtocol
from core.users.user_id import require_strict_user_id
from core.validation.integers import is_strict_int

__all__ = ("ocr_language_from_preferences", "resolve_user_ocr_language")


def ocr_language_from_preferences(preferences: JSONDict) -> str:
    if "settings" not in preferences:
        return DEFAULT_OCR_LANGUAGE
    settings = preferences["settings"]
    if not isinstance(settings, dict):
        raise StateError("Stored OCR settings must be a JSON object.")
    if "ocr_language" not in settings:
        return DEFAULT_OCR_LANGUAGE
    return require_ocr_language(settings["ocr_language"])


async def resolve_user_ocr_language(database_users: DatabaseUsersProtocol, user_id: int) -> str:
    if is_strict_int(user_id) and user_id == 0:
        return DEFAULT_OCR_LANGUAGE
    require_strict_user_id(user_id)
    preferences = await database_users.get_user_preferences(user_id)
    if preferences is None:
        raise NotFoundError("OCR extraction owner does not exist.")
    return ocr_language_from_preferences(preferences)
