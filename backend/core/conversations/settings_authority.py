"""SoAI - Conversation settings authority contract [backend/core/conversations/settings_authority.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from typing import Literal

    from core.types.json import JSONDict, JSONValue

    type SettingsAuthorityType = Literal[
        "conversation",
        "automation",
        "messaging_account",
    ]

__all__ = (
    "ConversationSettingsAuthority",
    "build_settings_authority_payload",
    "resolve_conversation_settings_authority",
)


@dataclass(frozen=True, slots=True)
class ConversationSettingsAuthority:
    authority_type: SettingsAuthorityType
    entity_id: str
    entity_label: str
    model_settings: JSONDict

    @property
    def is_read_only(self) -> bool:
        return self.authority_type != "conversation"

    @property
    def is_automation(self) -> bool:
        return self.authority_type == "automation"


def resolve_conversation_settings_authority(
    conversation_record: JSONDict,
) -> ConversationSettingsAuthority:
    conv_id = coerce_optional_trimmed_str(conversation_record.get("id"))
    if conv_id is None:
        raise StateError("Conversation settings authority requires a conversation id.")
    conversation_label = coerce_optional_trimmed_str(conversation_record.get("title")) or conv_id
    messaging_account_id = coerce_optional_trimmed_str(
        conversation_record.get("messaging_account_id"),
    )
    if messaging_account_id is not None:
        return ConversationSettingsAuthority(
            authority_type="messaging_account",
            entity_id=messaging_account_id,
            entity_label=_require_messaging_account_label(conversation_record),
            model_settings=_require_model_settings(
                conversation_record.get("messaging_account_model_settings"),
            ),
        )
    is_automation_value = conversation_record.get("is_automation")
    if is_automation_value == 1 or is_automation_value is True:
        return ConversationSettingsAuthority(
            authority_type="automation",
            entity_id=(
                coerce_optional_trimmed_str(conversation_record.get("automation_id")) or conv_id
            ),
            entity_label=(
                coerce_optional_trimmed_str(conversation_record.get("automation_title"))
                or conversation_label
            ),
            model_settings=_require_model_settings(conversation_record.get("model_settings")),
        )
    return ConversationSettingsAuthority(
        authority_type="conversation",
        entity_id=conv_id,
        entity_label=conversation_label,
        model_settings=_require_model_settings(conversation_record.get("model_settings")),
    )


def build_settings_authority_payload(
    authority: ConversationSettingsAuthority,
) -> JSONDict:
    return {
        "type": authority.authority_type,
        "entity_id": authority.entity_id,
        "entity_label": authority.entity_label,
        "read_only": authority.is_read_only,
    }


def _require_model_settings(value: JSONValue) -> JSONDict:
    model_settings = coerce_json_dict(value)
    if model_settings is None:
        raise StateError("Conversation settings authority found invalid model settings.")
    return model_settings


def _require_messaging_account_label(conversation_record: JSONDict) -> str:
    label = coerce_optional_trimmed_str(conversation_record.get("messaging_account_label"))
    if label is None:
        raise StateError("Messaging account settings authority requires an account label.")
    return label
