"""SoAI - Shared OpenAI streaming identity rewriting [backend/core/openai/streaming_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.sse_frame_payloads import parse_openai_sse_frame_payloads
from core.openai.sse_rewrite import rewrite_openai_sse_json_payload_frame
from core.types.json import JSONDict
from core.validation.integers import is_strict_int

__all__ = (
    "extract_stream_identity_from_frame",
    "rewrite_stream_identity_in_frame",
)


def extract_stream_identity_from_frame(frame: bytes) -> tuple[str | None, int | None]:
    for payload in parse_openai_sse_frame_payloads(frame):
        stream_id_value = payload.get("id")
        stream_id = (
            stream_id_value.strip()
            if isinstance(stream_id_value, str) and stream_id_value.strip()
            else None
        )
        created_value = payload.get("created")
        created = int(created_value) if is_strict_int(created_value) else None
        if stream_id is not None:
            return (stream_id, created)
    return (None, None)


def rewrite_stream_identity_in_frame(frame: bytes, *, stream_id: str, created: int | None) -> bytes:
    def rewrite_payload(payload: JSONDict) -> bool:
        prior_id = payload.get("id")
        payload["id"] = stream_id
        prior_created = payload.get("created")
        if created is not None and is_strict_int(prior_created):
            payload["created"] = created
        return payload.get("id") != prior_id or payload.get("created") != prior_created

    return rewrite_openai_sse_json_payload_frame(
        frame,
        rewrite_payload=rewrite_payload,
    )
