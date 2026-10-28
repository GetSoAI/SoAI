"""SoAI - Client-facing OpenAI response model identity [backend/core/openai/response_model_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.sse_frame_payloads import parse_openai_sse_frame_payloads
from core.serialization.json import serialize_json_compact_stable_strict
from core.streaming.sse_frames import extract_sse_data_payload_text
from core.types.json import JSONDict

__all__ = ("normalize_response_frame_model_identity", "normalize_response_model_identity")


def normalize_response_model_identity(payload: JSONDict, model: str | None) -> JSONDict:
    if not model:
        return payload
    normalized = payload
    if isinstance(payload.get("model"), str) and payload["model"] != model:
        normalized = {**payload, "model": model}
    response = payload.get("response")
    if (
        isinstance(response, dict)
        and isinstance(response.get("model"), str)
        and response["model"] != model
    ):
        normalized = {**normalized, "response": {**response, "model": model}}
    return normalized


def normalize_response_frame_model_identity(frame: str, model: str | None) -> str:
    if not model:
        return frame
    payloads = parse_openai_sse_frame_payloads(frame)
    if not payloads:
        return frame
    payload = payloads[0]
    normalized = normalize_response_model_identity(payload, model)
    if normalized is payload:
        return frame
    serialized = serialize_json_compact_stable_strict(normalized)
    lines: list[str] = []
    data_written = False
    for line in frame.splitlines(keepends=True):
        if extract_sse_data_payload_text(line) is None:
            lines.append(line)
        elif not data_written:
            lines.append(f"data: {serialized}\n")
            data_written = True
    return "".join(lines)
