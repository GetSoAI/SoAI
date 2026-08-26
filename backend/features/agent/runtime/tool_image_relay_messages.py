"""SoAI - Internal tool-image relay prompt messages [backend/features/agent/runtime/tool_image_relay_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.content_types import normalize_content_type
from core.files.inline_image_preparation import (
    DEFAULT_PROMPT_RELAY_IMAGE_MAX_PIXELS,
    prepare_inline_image_for_prompt_relay,
)
from core.openai.internal_message_metadata import SOAI_MESSAGE_TYPE_FIELD
from core.openai.token_accounting import count_prompt_occupancy_async
from core.serialization.base64_values import decode_base64_ascii
from features.agent.runtime.request_messages import strip_internal_message_metadata

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "TOOL_IMAGE_RELAY_MESSAGE_TYPE",
    "build_tool_image_relay_message",
    "build_tool_image_relay_message_for_prompt",
    "has_tool_image_relay_message",
    "is_tool_image_relay_message",
)

TOOL_IMAGE_RELAY_MESSAGE_TYPE: str = "tool_image_relay"


@dataclass(frozen=True, slots=True)
class ToolImagePayload:
    image_base64: str
    declared_content_type: str | None


def is_tool_image_relay_message(message: JSONDict) -> bool:
    return message.get(SOAI_MESSAGE_TYPE_FIELD) == TOOL_IMAGE_RELAY_MESSAGE_TYPE


def has_tool_image_relay_message(message_history: list[JSONDict]) -> bool:
    for message in message_history:
        if is_tool_image_relay_message(message):
            return True
    return False


def build_tool_image_relay_message(content: list[JSONDict]) -> JSONDict:
    return {
        "role": "user",
        "content": list(content),
        SOAI_MESSAGE_TYPE_FIELD: TOOL_IMAGE_RELAY_MESSAGE_TYPE,
    }


async def build_tool_image_relay_message_for_prompt(
    *,
    logger: LoggerProtocol,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    message_history: list[JSONDict],
    pending_messages: list[JSONDict],
    tool_results: list[JSONValue],
    max_prompt_tokens: int | None,
    max_encoded_chars: int,
    token_estimation_profile: TokenEstimationProfile,
    max_pixels: int = DEFAULT_PROMPT_RELAY_IMAGE_MAX_PIXELS,
) -> JSONDict | None:
    payloads = _collect_tool_image_payloads_from_results(tool_results)
    if not payloads:
        return None
    if max_prompt_tokens is None:
        logger.warning("Skipped tool image relay because no prompt token budget was available.")
        return None
    included_parts: list[JSONDict] = []
    for payload in payloads:
        remaining_encoded_chars = await _resolve_remaining_image_encoded_chars(
            logger=logger,
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            message_history=message_history,
            pending_messages=pending_messages,
            included_parts=included_parts,
            max_prompt_tokens=max_prompt_tokens,
            max_encoded_chars=max_encoded_chars,
            token_estimation_profile=token_estimation_profile,
        )
        if remaining_encoded_chars <= 0:
            break
        part = _build_tool_image_part(
            logger=logger,
            payload=payload,
            max_encoded_chars=remaining_encoded_chars,
            max_pixels=max_pixels,
        )
        if part is None:
            continue
        candidate_message = build_tool_image_relay_message(included_parts + [part])
        candidate_payload = dict(base_request_payload)
        candidate_payload["messages"] = strip_internal_message_metadata(
            list(message_history) + list(pending_messages) + [candidate_message],
        )
        occupancy = await count_prompt_occupancy_async(
            prompt_token_counter=prompt_token_counter,
            request_payload=candidate_payload,
            token_estimation_profile=token_estimation_profile,
        )
        if occupancy.capped:
            logger.warning(
                "Stopped tool image relay inclusion because prompt token counting capped (reason=%s).",
                occupancy.capped_reason,
            )
            break
        prompt_tokens = occupancy.prompt_tokens
        if prompt_tokens > max_prompt_tokens:
            continue
        included_parts.append(part)
    if not included_parts:
        return None
    return build_tool_image_relay_message(included_parts)


def _collect_tool_image_payloads_from_results(
    tool_results: list[JSONValue],
) -> list[ToolImagePayload]:
    payloads: list[ToolImagePayload] = []
    for tool_result in tool_results:
        _collect_tool_image_payloads(tool_result, payloads)
    return payloads


async def _resolve_remaining_image_encoded_chars(
    *,
    logger: LoggerProtocol,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    message_history: list[JSONDict],
    pending_messages: list[JSONDict],
    included_parts: list[JSONDict],
    max_prompt_tokens: int,
    max_encoded_chars: int,
    token_estimation_profile: TokenEstimationProfile,
) -> int:
    current_payload = dict(base_request_payload)
    current_messages = list(message_history) + list(pending_messages)
    if included_parts:
        current_messages.append(build_tool_image_relay_message(included_parts))
    current_payload["messages"] = strip_internal_message_metadata(current_messages)
    occupancy = await count_prompt_occupancy_async(
        prompt_token_counter=prompt_token_counter,
        request_payload=current_payload,
        token_estimation_profile=token_estimation_profile,
    )
    if occupancy.capped:
        logger.warning(
            "Stopped tool image relay inclusion because prompt token counting capped (reason=%s).",
            occupancy.capped_reason,
        )
        return 0
    remaining_tokens = int(max_prompt_tokens) - int(occupancy.prompt_tokens)
    if remaining_tokens <= 0:
        return 0
    return min(int(max_encoded_chars), remaining_tokens * 4)


def _collect_tool_image_payloads(
    value: JSONValue,
    payloads: list[ToolImagePayload],
) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_tool_image_payloads(item, payloads)
        return
    if not isinstance(value, dict):
        return
    image_base64 = value.get("image_base64")
    if isinstance(image_base64, str) and image_base64.strip():
        payloads.append(
            ToolImagePayload(
                image_base64=image_base64.strip(),
                declared_content_type=_resolve_declared_content_type(value),
            ),
        )
    for key in sorted(value.keys()):
        if key == "image_base64":
            continue
        _collect_tool_image_payloads(value.get(key), payloads)


def _resolve_declared_content_type(value: JSONDict) -> str | None:
    for key in ("content_type", "mime_type", "mime", "media_type"):
        raw = value.get(key)
        if isinstance(raw, str) and raw.strip():
            normalized = normalize_content_type(raw)
            return normalized or None
    return None


def _build_tool_image_part(
    *,
    logger: LoggerProtocol,
    payload: ToolImagePayload,
    max_encoded_chars: int,
    max_pixels: int,
) -> JSONDict | None:
    try:
        image_bytes = decode_base64_ascii(
            payload.image_base64,
            error_message="Tool image relay payload has invalid base64 data.",
        )
    except ValidationError:
        logger.warning("Dropped tool image relay payload with invalid base64 data.")
        return None
    prepared, failure_reason = prepare_inline_image_for_prompt_relay(
        image_bytes=image_bytes,
        declared_content_type=payload.declared_content_type,
        max_encoded_chars=max_encoded_chars,
        max_pixels=max_pixels,
    )
    if prepared is None:
        logger.warning(
            "Dropped tool image relay payload because image preparation failed (%s).",
            failure_reason or "unknown",
        )
        return None
    encoded = prepared.payload.get("image_base64")
    if not isinstance(encoded, str) or not encoded:
        logger.warning("Dropped tool image relay payload because inline encoding failed.")
        return None
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{prepared.content_type};base64,{encoded}",
        },
    }
