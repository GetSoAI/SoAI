"""SoAI - Image URL delta extraction for OpenAI streaming SSE events [backend/core/openai/streaming_image_segments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterator

from core.openai.sse_frame_payloads import parse_openai_sse_frame_payloads
from core.types.json import JSONDict, JSONValue

__all__ = ("extract_openai_streaming_image_urls",)


def _iter_image_urls_from_content(value: JSONValue) -> Iterator[str]:
    if not isinstance(value, list):
        return
    for segment in value:
        if not isinstance(segment, dict):
            continue
        segment_type = segment.get("type")
        normalized_type = segment_type.strip().lower() if isinstance(segment_type, str) else ""
        if normalized_type != "image_url":
            continue
        image_url_value = segment.get("image_url")
        if not isinstance(image_url_value, dict):
            continue
        url_value = image_url_value.get("url")
        url = url_value.strip() if isinstance(url_value, str) else ""
        if url:
            yield url


def _iter_image_urls_from_choice(choice: JSONDict) -> Iterator[str]:
    delta_value = choice.get("delta")
    delta = delta_value if isinstance(delta_value, dict) else None
    if delta is not None:
        yield from _iter_image_urls_from_content(delta.get("content"))
    message_value = choice.get("message")
    message = message_value if isinstance(message_value, dict) else None
    if message is not None:
        yield from _iter_image_urls_from_content(message.get("content"))


def extract_openai_streaming_image_urls(sse_frame: str) -> tuple[str, ...]:
    if not sse_frame:
        return ()
    urls: list[str] = []
    for decoded_dict in parse_openai_sse_frame_payloads(sse_frame):
        choices_value = decoded_dict.get("choices")
        if not isinstance(choices_value, list) or not choices_value:
            continue
        for choice_item in choices_value:
            if not isinstance(choice_item, dict):
                continue
            urls.extend(_iter_image_urls_from_choice(choice_item))
    return tuple(urls)
