"""SoAI - Conversation regeneration admission normalization [backend/database/repositories/users/conversation_input_regeneration_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from core.validation.strings import coerce_required_non_empty_str
from database.repositories.users.conversation_input_validation import (
    now_ms,
    require_client_id,
    require_source_key,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ConversationRegenerationAdmission",
    "normalize_conversation_regeneration_admission",
)


@dataclass(frozen=True, slots=True)
class ConversationRegenerationAdmission:
    input_id: str
    request_id: str
    source_key: str
    client_id: str
    client_request_id: str
    regeneration_request_json: str
    model_settings_json: str
    settings_authority_json: str
    accepted_at_ms: int


def normalize_conversation_regeneration_admission(
    *,
    conv_id: str,
    client_id: str,
    client_request_id: str,
    regeneration_request: JSONDict,
    model_settings: JSONDict,
    settings_authority: JSONDict,
) -> ConversationRegenerationAdmission:
    normalized_client_id = require_client_id(client_id)
    normalized_request_id = coerce_required_non_empty_str(
        client_request_id,
        label="client_request_id",
    )
    input_id = f"cinput_{uuid.uuid4().hex[:16]}"
    return ConversationRegenerationAdmission(
        input_id=input_id,
        request_id=f"chat_{input_id}",
        source_key=require_source_key(
            f"regenerate:{conv_id}:{normalized_client_id}:{normalized_request_id}",
        ),
        client_id=normalized_client_id,
        client_request_id=normalized_request_id,
        regeneration_request_json=serialize_json_compact_stable(regeneration_request),
        model_settings_json=serialize_json_compact_stable(model_settings),
        settings_authority_json=serialize_json_compact_stable(settings_authority),
        accepted_at_ms=now_ms(),
    )
