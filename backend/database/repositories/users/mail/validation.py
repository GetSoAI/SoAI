"""SoAI - Mail repository validation helpers [backend/database/repositories/users/mail/validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from database.core.json_codec import serialize_required_json_list_field
from database.repositories.users.account_validation import require_text

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "require_json_list",
    "require_protocol",
    "require_security",
)


def require_protocol(value: JSONValue) -> str:
    normalized = require_text(value, "protocol")
    if normalized not in {"imap", "pop3"}:
        raise ValidationError("protocol must be imap or pop3.")
    return normalized


def require_security(value: JSONValue, label: str) -> str:
    normalized = require_text(value, label)
    if normalized not in {"tls", "starttls"}:
        raise ValidationError(f"{label} must be tls or starttls.")
    return normalized


def require_json_list(value: JSONValue, label: str) -> str:
    return serialize_required_json_list_field(
        value,
        error_message=f"{label} must be a list.",
    )
