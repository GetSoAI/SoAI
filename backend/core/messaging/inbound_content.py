"""SoAI - Messaging inbound content normalization [backend/core/messaging/inbound_content.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.epoch import EPOCH_MS_MIN

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "attachment_text",
    "bounded_trimmed_text",
    "compose_content",
    "identifier_text",
    "provider_epoch_seconds_ms",
    "trimmed_text",
)


def bounded_trimmed_text(value: JSONValue, maximum_length: int) -> str | None:
    normalized = trimmed_text(value)
    if normalized is None or len(normalized) > maximum_length:
        return None
    return normalized


def trimmed_text(value: JSONValue) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def identifier_text(value: JSONValue) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        return trimmed_text(value)
    if isinstance(value, int | float):
        return str(value)
    return None


def provider_epoch_seconds_ms(value: JSONValue) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        seconds = value
    elif isinstance(value, str) and value.isdigit():
        seconds = int(value)
    else:
        return None
    timestamp_ms = seconds * 1000
    return timestamp_ms if timestamp_ms >= EPOCH_MS_MIN else None


def attachment_text(attachments: list[JSONDict]) -> tuple[str, ...]:
    summaries: list[str] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        url_value = trimmed_text(attachment.get("url"))
        filename_value = trimmed_text(attachment.get("filename"))
        if filename_value and url_value:
            summaries.append(f"{filename_value}: {url_value}")
            continue
        if filename_value:
            summaries.append(filename_value)
            continue
        if url_value:
            summaries.append(url_value)
    return tuple(summaries)


def compose_content(text: str | None, attachments: tuple[str, ...]) -> str:
    parts: list[str] = []
    if text:
        parts.append(text)
    for attachment in attachments:
        parts.append(f"[attachment] {attachment}")
    return "\n".join(parts).strip()
