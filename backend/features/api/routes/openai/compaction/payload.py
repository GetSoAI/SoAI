"""SoAI - Compaction payload building [backend/features/api/routes/openai/compaction/payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_summary_payload",)


def build_summary_payload(
    *,
    model: str,
    system_prompt_text: str,
    chunk: list[JSONDict],
    max_output_tokens: int,
    disable_reasoning: bool = False,
) -> JSONDict:
    serialized = serialize_json_compact_stable(chunk)
    user_text = f"<conversation_messages_json>\n{serialized}\n</conversation_messages_json>"
    payload: JSONDict = {
        "model": model,
        "stream": True,
        "temperature": 0,
        "max_tokens": int(max_output_tokens),
        "messages": [
            {"role": "system", "content": str(system_prompt_text or "").strip()},
            {"role": "user", "content": user_text},
        ],
    }
    if disable_reasoning:
        payload["reasoning_effort"] = "none"
    return payload
