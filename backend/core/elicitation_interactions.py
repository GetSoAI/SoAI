"""SoAI - Shared elicitation interaction helpers [backend/core/elicitation_interactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.elicitation_ask_user import ASK_USER_INTERACTION_TYPE
from core.elicitation_vault_secret_request import CREDENTIAL_REQUEST_INTERACTION_TYPE
from core.errors.exceptions import ValidationError
from core.tool_approval.constants import TOOL_APPROVAL_INTERACTION_TYPE
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SUPPORTED_CONVERSATION_INTERACTION_TYPES",
    "extract_notification_id",
    "normalize_interaction_type",
    "require_supported_interaction_type",
    "resolve_cancelled_interaction_result",
    "resolve_interaction_error_messages",
)

SUPPORTED_CONVERSATION_INTERACTION_TYPES: frozenset[str] = frozenset(
    {
        ASK_USER_INTERACTION_TYPE,
        CREDENTIAL_REQUEST_INTERACTION_TYPE,
        TOOL_APPROVAL_INTERACTION_TYPE,
    },
)


def normalize_interaction_type(value: JSONValue) -> str | None:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None or normalized not in SUPPORTED_CONVERSATION_INTERACTION_TYPES:
        return None
    return normalized


def require_supported_interaction_type(interaction_type: str) -> str:
    normalized = normalize_interaction_type(interaction_type)
    if normalized is None:
        raise ValidationError("Unsupported interaction type.")
    return normalized


def resolve_interaction_error_messages(interaction_type: str) -> tuple[str, str]:
    normalized = require_supported_interaction_type(interaction_type)
    if normalized == ASK_USER_INTERACTION_TYPE:
        return ("Ask-user prompt task not found.", "Task is not an ask_user interaction.")
    if normalized == CREDENTIAL_REQUEST_INTERACTION_TYPE:
        return (
            "Vault secret prompt task not found.",
            "Task is not a vault_secret_request interaction.",
        )
    return ("Tool approval task not found.", "Task is not a tool approval interaction.")


def resolve_cancelled_interaction_result(interaction_type: str) -> JSONDict:
    normalized = require_supported_interaction_type(interaction_type)
    if normalized == ASK_USER_INTERACTION_TYPE:
        return {"answers": {}}
    if normalized == CREDENTIAL_REQUEST_INTERACTION_TYPE:
        return {"secret_handle": None, "saved_credential_id": None}
    return {"approved": False, "remember": False}


def extract_notification_id(metadata: Mapping[str, JSONValue]) -> str | None:
    return coerce_optional_trimmed_str(metadata.get("notification_id"))
