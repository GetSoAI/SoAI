"""SoAI - Stream prefix privacy partitioning [backend/features/agent/runtime/injected_prompt_echo_prefix_partition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.reasoning_text import REASONING_FIELD_NAMES
from core.openai.sse_frame_payloads import parse_openai_sse_frame_payloads
from core.openai.sse_rewrite import rewrite_openai_sse_json_payload_frame
from core.types.json import JSONDict

__all__ = ("split_prefix_pending_frame",)

_PREFIX_SENSITIVE_FIELDS = frozenset(
    ("content", "text", "output_text", "tool_calls", "function_call"),
)
_SAFE_PREFIX_FIELDS = (*REASONING_FIELD_NAMES, "role")


def _payload_requires_prefix_decision(payload: JSONDict) -> bool:
    if _PREFIX_SENSITIVE_FIELDS.intersection(payload):
        return True
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return False
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        if choice.get("finish_reason") is not None:
            return True
        if _PREFIX_SENSITIVE_FIELDS.intersection(choice):
            return True
        for source_name in ("delta", "message"):
            source = choice.get(source_name)
            if isinstance(source, dict) and _PREFIX_SENSITIVE_FIELDS.intersection(source):
                return True
    return False


def _safe_prefix_payload(payload: JSONDict) -> JSONDict | None:
    safe_payload = {key: payload[key] for key in _SAFE_PREFIX_FIELDS if key in payload}
    choices = payload.get("choices")
    if isinstance(choices, list):
        safe_choices: list[JSONDict] = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            safe_sources: JSONDict = {}
            for source_name in ("delta", "message"):
                source = choice.get(source_name)
                if not isinstance(source, dict):
                    continue
                safe_source = {key: source[key] for key in _SAFE_PREFIX_FIELDS if key in source}
                if safe_source:
                    safe_sources[source_name] = safe_source
            if not safe_sources:
                continue
            safe_choice: JSONDict = {}
            if "index" in choice:
                safe_choice["index"] = choice["index"]
            safe_choice.update(safe_sources)
            safe_choices.append(safe_choice)
        if safe_choices:
            safe_payload["choices"] = safe_choices
    if not safe_payload:
        return None
    for key in ("id", "object", "created", "model", "system_fingerprint"):
        if key in payload:
            safe_payload[key] = payload[key]
    return safe_payload


def split_prefix_pending_frame(frame: bytes) -> tuple[bytes | None, bytes | None]:
    payloads = parse_openai_sse_frame_payloads(frame)
    if len(payloads) != 1:
        return None, frame
    payload = payloads[0]
    if not _payload_requires_prefix_decision(payload):
        return frame, None
    safe_payload = _safe_prefix_payload(payload)
    if safe_payload is None:
        return None, frame

    def retain_safe_fields(frame_payload: JSONDict) -> bool:
        frame_payload.clear()
        frame_payload.update(safe_payload)
        return True

    def remove_safe_fields(frame_payload: JSONDict) -> bool:
        changed = False
        for key in _SAFE_PREFIX_FIELDS:
            if key in frame_payload:
                frame_payload.pop(key)
                changed = True
        choices = frame_payload.get("choices")
        if not isinstance(choices, list):
            return changed
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            for source_name in ("delta", "message"):
                source = choice.get(source_name)
                if not isinstance(source, dict):
                    continue
                for key in _SAFE_PREFIX_FIELDS:
                    if key in source:
                        source.pop(key)
                        changed = True
        return changed

    safe_frame = rewrite_openai_sse_json_payload_frame(
        frame,
        rewrite_payload=retain_safe_fields,
    )
    pending_frame = rewrite_openai_sse_json_payload_frame(
        frame,
        rewrite_payload=remove_safe_fields,
    )
    return safe_frame, pending_frame
