"""SoAI - Conversation input content fingerprinting [backend/database/repositories/users/conversation_input_fingerprint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from database.repositories.users.conversation_input_attachment_semantics import (
    conversation_input_content_signature,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_conversation_input_content_fingerprint",)


def build_conversation_input_content_fingerprint(
    *,
    input_type: str,
    text: str,
    attachment_content: list[JSONValue],
    model_settings: JSONDict | None,
    source_metadata: JSONDict,
    media_descriptors: list[JSONValue],
    regeneration_request: JSONDict | None = None,
) -> str:
    payload: JSONDict = {
        "input_type": input_type,
        "text": text,
        "attachment_signature": conversation_input_content_signature(
            attachment_content,
            label="conversation input attachment_content entry",
        ),
        "model_settings": model_settings,
        "source_metadata": source_metadata,
        "media_descriptors": media_descriptors,
    }
    if regeneration_request is not None:
        payload["regeneration_request"] = regeneration_request
    serialized = serialize_json_compact_stable(payload)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
