"""SoAI - Canonical conversation source metadata [backend/core/conversations/conversation_source.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Literal

    from core.types.json import JSONDict, JSONValue

    type MessagingPlatform = Literal["telegram", "whatsapp", "discord"]

__all__ = (
    "ConversationSourceMetadata",
    "build_conversation_source_metadata",
    "resolve_conversation_source_metadata",
)


@dataclass(frozen=True, slots=True)
class ConversationSourceMetadata:
    is_messaging: bool
    messaging_platform: MessagingPlatform | None
    messaging_account_label: str | None
    messaging_account_snapshot_id: str | None

    def to_payload(self) -> JSONDict:
        return {
            "is_messaging": self.is_messaging,
            "messaging_platform": self.messaging_platform,
            "messaging_account_label": self.messaging_account_label,
            "messaging_account_snapshot_id": self.messaging_account_snapshot_id,
        }


def build_conversation_source_metadata(
    *,
    is_messaging: bool,
    messaging_platform: str | None,
    messaging_account_label: str | None,
    messaging_account_snapshot_id: str | None,
) -> ConversationSourceMetadata:
    normalized_platform = coerce_optional_trimmed_str(messaging_platform)
    normalized_label = coerce_optional_trimmed_str(messaging_account_label)
    normalized_snapshot_id = coerce_optional_trimmed_str(messaging_account_snapshot_id)
    complete_identity = (
        normalized_platform in ("telegram", "whatsapp", "discord")
        and normalized_label is not None
        and normalized_snapshot_id is not None
    )
    empty_identity = (
        normalized_platform is None and normalized_label is None and normalized_snapshot_id is None
    )
    if (is_messaging and not complete_identity) or (not is_messaging and not empty_identity):
        raise StateError("Conversation Messaging identity is inconsistent.")
    if normalized_platform not in (None, "telegram", "whatsapp", "discord"):
        raise StateError("Conversation Messaging platform is invalid.")
    resolved_platform: MessagingPlatform | None
    if normalized_platform == "telegram":
        resolved_platform = "telegram"
    elif normalized_platform == "whatsapp":
        resolved_platform = "whatsapp"
    elif normalized_platform == "discord":
        resolved_platform = "discord"
    else:
        resolved_platform = None
    return ConversationSourceMetadata(
        is_messaging=is_messaging,
        messaging_platform=resolved_platform,
        messaging_account_label=normalized_label,
        messaging_account_snapshot_id=normalized_snapshot_id,
    )


def resolve_conversation_source_metadata(
    conversation_record: Mapping[str, JSONValue],
) -> ConversationSourceMetadata:
    is_messaging_value = conversation_record.get("is_messaging")
    if not isinstance(is_messaging_value, bool):
        raise StateError("Conversation is_messaging is invalid.")
    return build_conversation_source_metadata(
        is_messaging=is_messaging_value,
        messaging_platform=_require_optional_source_str(
            conversation_record.get("messaging_platform"),
            "platform",
        ),
        messaging_account_label=_require_optional_source_str(
            conversation_record.get("messaging_account_label"),
            "account label",
        ),
        messaging_account_snapshot_id=_require_optional_source_str(
            conversation_record.get("messaging_account_snapshot_id"),
            "account snapshot id",
        ),
    )


def _require_optional_source_str(value: JSONValue, label: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise StateError(f"Conversation Messaging {label} is invalid.")
