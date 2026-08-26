"""SoAI - Conversation model settings materialization [backend/core/conversations/conversation_model_settings_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.conversation_settings_resolution import (
    apply_resolved_chat_settings,
    resolve_chat_settings,
)
from core.errors.exceptions import StateError
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.conversations.protocols_database_defaults import (
        DatabaseChatIdentityDefaultsProtocol,
        DatabaseChatModelDefaultsProtocol,
    )
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "require_conversation_model_settings",
    "resolve_conversation_model_settings",
    "resolve_optional_conversation_model_settings",
)


def require_conversation_model_settings(
    model_settings_snapshot: JSONValue,
    *,
    error_message: str = "Conversation model_settings payload is invalid.",
    exception_type: type[Exception] = StateError,
) -> JSONDict:
    model_settings = coerce_json_dict(model_settings_snapshot)
    if model_settings is None:
        raise exception_type(error_message)
    return model_settings


def resolve_optional_conversation_model_settings(
    model_settings_snapshot: JSONValue,
    *,
    error_message: str = "Conversation model_settings payload is invalid.",
    exception_type: type[Exception] = StateError,
) -> JSONDict:
    if model_settings_snapshot is None:
        return {}
    return require_conversation_model_settings(
        model_settings_snapshot,
        error_message=error_message,
        exception_type=exception_type,
    )


async def resolve_conversation_model_settings(
    *,
    user_id: int,
    model_settings_snapshot: JSONValue,
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol,
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol,
) -> JSONDict:
    model_settings = dict(
        require_conversation_model_settings(
            model_settings_snapshot,
            error_message="Conversation model settings are invalid.",
        ),
    )
    model_value = model_settings.get("model")
    model_id = model_value.strip() if isinstance(model_value, str) and model_value.strip() else None
    resolved = await resolve_chat_settings(
        user_id=user_id,
        model_id=model_id,
        conversation_model_settings=model_settings,
        database_chat_identity_defaults=database_chat_identity_defaults,
        database_chat_model_defaults=database_chat_model_defaults,
    )
    return apply_resolved_chat_settings(
        model_settings=model_settings,
        resolved=resolved,
    )
