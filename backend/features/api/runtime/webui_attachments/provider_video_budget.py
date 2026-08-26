"""SoAI - Request-wide provider video frame allocation [backend/features/api/runtime/webui_attachments/provider_video_budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.message_content_parts import iter_message_content_parts

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.webui_attachments.provider_video_settings import (
        ProviderVideoSettings,
    )

__all__ = (
    "ProviderVideoAllocation",
    "build_provider_video_allocations",
    "provider_video_part_key",
)


@dataclass(frozen=True, slots=True)
class ProviderVideoAllocation:
    maximum_frames: int
    maximum_encoded_chars: int


def provider_video_part_key(part: JSONDict) -> str | None:
    if part.get("preview_type") != "video":
        return None
    part_type = part.get("type")
    if part_type == "soai_file":
        attachment_id = part.get("attachment_id")
        if isinstance(attachment_id, str) and attachment_id:
            return f"file:{attachment_id}"
        return None
    if part_type == "soai_path":
        source_reference = part.get("source_reference")
        target_fingerprint = part.get("target_fingerprint")
        source_value = source_reference.get("value") if isinstance(source_reference, dict) else None
        fingerprint_value = (
            target_fingerprint.get("value") if isinstance(target_fingerprint, dict) else None
        )
        if isinstance(source_value, str) and isinstance(fingerprint_value, str):
            return f"path:{source_value}:{fingerprint_value}"
    return None


def _ordered_distinct_video_keys(messages: list[JSONDict]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for part in iter_message_content_parts(messages):
        key = provider_video_part_key(part)
        if key is None or key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    ordered.reverse()
    return ordered


def build_provider_video_allocations(
    messages: list[JSONDict],
    settings: ProviderVideoSettings,
) -> dict[str, ProviderVideoAllocation]:
    newest_keys = _ordered_distinct_video_keys(messages)
    selected_keys = newest_keys[: settings.max_frames_per_request]
    if not selected_keys:
        return {}
    frame_counts = {key: 1 for key in selected_keys}
    remaining_frames = settings.max_frames_per_request - len(selected_keys)
    while remaining_frames > 0:
        for key in selected_keys:
            if remaining_frames <= 0:
                break
            frame_counts[key] += 1
            remaining_frames -= 1
    base_chars, extra_chars = divmod(
        settings.max_encoded_chars_per_request,
        len(selected_keys),
    )
    return {
        key: ProviderVideoAllocation(
            maximum_frames=frame_counts[key],
            maximum_encoded_chars=base_chars + (1 if index < extra_chars else 0),
        )
        for index, key in enumerate(selected_keys)
    }
