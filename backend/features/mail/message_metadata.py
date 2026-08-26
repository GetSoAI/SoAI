"""SoAI - Mail message metadata helpers [backend/features/mail/message_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import re
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from typing import TYPE_CHECKING

from core.timing.datetime_conversion import datetime_to_epoch_ms
from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = (
    "build_thread_id",
    "extract_references",
    "normalize_message_id",
    "parse_address_header",
    "parse_header_datetime_to_epoch_ms",
)


def parse_address_header(values: Iterable[str]) -> list[JSONDict]:
    parsed = getaddresses(list(values))
    addresses: list[JSONDict] = []
    for display_name, email_address in parsed:
        normalized_email = str(email_address or "").strip()
        if not normalized_email:
            continue
        normalized_name = str(display_name or "").strip() or None
        addresses.append({"email": normalized_email, "name": normalized_name})
    return addresses


def normalize_message_id(value: JSONValue) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    matches = re.findall(r"<[^>]+>", normalized)
    if matches:
        return str(matches[0])
    return normalized


def extract_references(message: Message) -> list[str]:
    raw_value = message.get("References")
    if not isinstance(raw_value, str) or not raw_value.strip():
        return []
    return [item.strip() for item in re.findall(r"<[^>]+>", raw_value) if item.strip()]


def build_thread_id(
    *,
    references: list[str],
    in_reply_to_message_id: str | None,
    rfc822_message_id: str | None,
    subject: str,
) -> str:
    root_token = references[0] if references else None
    if root_token is None:
        root_token = in_reply_to_message_id
    if root_token is None:
        root_token = rfc822_message_id
    if root_token is None:
        root_token = subject
    digest = hashlib.sha256(root_token.encode("utf-8")).hexdigest()
    return f"thread_{digest[:24]}"


def parse_header_datetime_to_epoch_ms(value: JSONValue) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    return datetime_to_epoch_ms(parsed)
