"""SoAI - Messaging provider credential field validation [backend/core/messaging/credential_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "require_messaging_credential",
    "require_telegram_bot_token",
    "require_whatsapp_access_token",
    "require_whatsapp_api_version",
)

WHATSAPP_API_VERSION_PATTERN = r"v[1-9][0-9]*\.[0-9]+"


def require_messaging_credential(
    credentials: JSONDict,
    key: str,
    label: str,
    *,
    maximum_length: int,
) -> str:
    normalized = coerce_optional_trimmed_str(credentials.get(key))
    if normalized is None or len(normalized) > maximum_length:
        raise ValidationError(f"{label} is required and must be valid.")
    return normalized


def require_telegram_bot_token(credentials: JSONDict) -> str:
    return require_messaging_credential(
        credentials,
        "bot_token",
        "Telegram bot token",
        maximum_length=512,
    )


def require_whatsapp_access_token(credentials: JSONDict) -> str:
    return require_messaging_credential(
        credentials,
        "access_token",
        "WhatsApp access token",
        maximum_length=2048,
    )


def require_whatsapp_api_version(credentials: JSONDict) -> str:
    api_version = require_messaging_credential(
        credentials,
        "api_version",
        "WhatsApp API version",
        maximum_length=32,
    )
    if re.fullmatch(WHATSAPP_API_VERSION_PATTERN, api_version) is None:
        raise ValidationError("WhatsApp API version is invalid.")
    return api_version
