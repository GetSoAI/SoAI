"""SoAI - Messaging account invariant validation [backend/core/messaging/account_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.messaging.account_models import MessagingAccountFence, MessagingAuthorizedSender
from core.openai.model_settings_validation import validate_model_settings
from core.types.json import is_json_dict
from core.validation.record_fields import require_int
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.messaging.account_models import (
        MessagingAccountLifecycleState,
        MessagingAccountLocale,
    )
    from core.types.json import JSONDict

__all__ = (
    "require_messaging_account_fence",
    "require_messaging_account_label",
    "require_messaging_account_id",
    "require_messaging_account_lifecycle_state",
    "require_messaging_account_locale",
    "require_messaging_credentials",
    "require_messaging_platform",
    "require_messaging_principal_id",
    "validate_messaging_authorized_senders",
    "validate_messaging_model_settings",
)


def require_messaging_account_fence(account: JSONDict) -> MessagingAccountFence:
    account_id = account.get("account_id")
    platform = account.get("platform")
    if not isinstance(account_id, str) or not isinstance(platform, str):
        raise ValidationError("Messaging account identity is invalid.")
    return MessagingAccountFence(
        user_id=require_int(
            account.get("user_id"),
            label="Messaging account owner",
            build_error=ValidationError,
            minimum=1,
        ),
        account_id=require_messaging_account_id(account_id),
        platform=require_messaging_platform(platform),
        revision=require_int(
            account.get("revision"),
            label="Messaging account revision",
            build_error=ValidationError,
            minimum=1,
        ),
        lifecycle_generation=require_int(
            account.get("lifecycle_generation"),
            label="Messaging account lifecycle generation",
            build_error=ValidationError,
            minimum=0,
        ),
    )


def require_messaging_platform(value: str) -> MessagingPlatform:
    normalized = coerce_optional_trimmed_str(value)
    if normalized == "telegram":
        return "telegram"
    if normalized == "whatsapp":
        return "whatsapp"
    if normalized == "discord":
        return "discord"
    raise ValidationError("Messaging platform is invalid.")


def require_messaging_account_label(value: str) -> str:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None or len(normalized) > 120:
        raise ValidationError("Messaging account label must contain 1 to 120 characters.")
    return normalized


def require_messaging_account_id(value: str) -> str:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None or len(normalized) > 120:
        raise ValidationError("Messaging account id is invalid.")
    return normalized


def require_messaging_principal_id(value: str, *, label: str) -> str:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None or len(normalized) > 255:
        raise ValidationError(f"{label} must contain 1 to 255 characters.")
    return normalized


def require_messaging_account_locale(value: str) -> MessagingAccountLocale:
    if value == "en":
        return "en"
    if value == "it":
        return "it"
    raise ValidationError("Messaging account locale is invalid.")


def require_messaging_account_lifecycle_state(value: str) -> MessagingAccountLifecycleState:
    if value == "enabled":
        return "enabled"
    if value == "disabled":
        return "disabled"
    if value == "deleting":
        return "deleting"
    if value == "degraded":
        return "degraded"
    raise ValidationError("Messaging account lifecycle state is invalid.")


def require_messaging_credentials(value: JSONDict) -> JSONDict:
    if not is_json_dict(value) or not value:
        raise ValidationError("Messaging account credentials must be a non-empty object.")
    return dict(value)


def validate_messaging_model_settings(value: JSONDict) -> JSONDict:
    return validate_model_settings(value)


def validate_messaging_authorized_senders(
    values: tuple[MessagingAuthorizedSender, ...],
) -> tuple[MessagingAuthorizedSender, ...]:
    normalized: list[MessagingAuthorizedSender] = []
    seen: set[str] = set()
    for value in values:
        sender_id = require_messaging_principal_id(
            value.sender_id,
            label="Messaging authorized sender id",
        )
        display_label = coerce_optional_trimmed_str(value.display_label)
        if display_label is not None and len(display_label) > 255:
            raise ValidationError(
                "Messaging authorized sender label must contain at most 255 characters.",
            )
        if sender_id in seen:
            raise ValidationError("Messaging authorized sender ids must be unique.")
        seen.add(sender_id)
        normalized.append(
            MessagingAuthorizedSender(
                sender_id=sender_id,
                display_label=display_label,
            ),
        )
    return tuple(normalized)
