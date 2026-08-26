"""SoAI - OpenAI request/payload normalization and validation primitives [backend/core/openai/payload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.chat_message_validation import validate_chat_message_dict
from core.openai.message_payload_access import get_openai_payload_message_dicts
from core.openai.model_settings_validation import validate_model_settings
from core.openai.payload_sanitization import sanitize_openai_request_messages

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk
    from core.types.json import JSONDict

__all__ = (
    "RERANK_API_PROVIDERS",
    "decode_streaming_text_chunk",
    "normalize_inference_payload_messages",
    "sanitize_openai_request_messages",
    "validate_model_settings",
)

RERANK_API_PROVIDERS = frozenset(
    ("cohere", "jina", "voyage", "mixedbread.ai", "pinecone", "isaacus"),
)


def decode_streaming_text_chunk(chunk: StreamChunk) -> str | None:
    try:
        if isinstance(chunk, bytes):
            return chunk.decode("utf-8")
        if isinstance(chunk, bytearray):
            return bytes(chunk).decode("utf-8")
        if isinstance(chunk, memoryview):
            return chunk.tobytes().decode("utf-8")
    except UnicodeDecodeError:
        return None
    if isinstance(chunk, str):
        return chunk
    return None


def normalize_inference_payload_messages(payload: JSONDict) -> JSONDict:
    messages = get_openai_payload_message_dicts(payload)
    if messages is None:
        return payload
    for index, message in enumerate(messages):
        if "content" not in message:
            role_value = message.get("role")
            role = role_value.strip() if isinstance(role_value, str) else ""
            if role == "assistant":
                message["content"] = None
            else:
                raise ValidationError(
                    f"Message at index {index} missing 'content'.",
                    details={"param": f"messages[{index}].content"},
                )
        validate_chat_message_dict(message, message_index=index)
    return payload
