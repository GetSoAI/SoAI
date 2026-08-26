"""SoAI - Mail message listing helpers [backend/features/mail/message_listing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json import JSONValue
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict

__all__ = (
    "build_cache_coverage",
    "filter_messages",
    "folder_sort_key",
    "message_sort_key",
)


def folder_sort_key(item: JSONDict, order_by: str) -> tuple[str | int, str]:
    sort_value = item.get(order_by)
    if isinstance(sort_value, int):
        return (sort_value, str(item.get("folder_id") or ""))
    if isinstance(sort_value, str):
        return (sort_value.lower(), str(item.get("folder_id") or ""))
    return ("", str(item.get("folder_id") or ""))


def message_sort_key(item: JSONDict, order_by: str) -> tuple[str | int, str]:
    if order_by == "from":
        from_value = item.get("from")
        if isinstance(from_value, list) and from_value:
            first = from_value[0]
            if isinstance(first, dict):
                email_value = first.get("email")
                if isinstance(email_value, str):
                    return (email_value.lower(), str(item.get("message_id") or ""))
        return ("", str(item.get("message_id") or ""))
    sort_value = item.get(order_by)
    if isinstance(sort_value, int):
        return (sort_value, str(item.get("message_id") or ""))
    if isinstance(sort_value, str):
        return (sort_value.lower(), str(item.get("message_id") or ""))
    return ("", str(item.get("message_id") or ""))


def filter_messages(messages: list[JSONDict], arguments: JSONDict) -> list[JSONDict]:
    filtered = list(messages)
    thread_id = coerce_optional_trimmed_str(arguments.get("thread_id"))
    if thread_id is not None:
        filtered = [
            message for message in filtered if str(message.get("thread_id") or "") == thread_id
        ]
    query = coerce_optional_trimmed_str(arguments.get("query"))
    if query is not None:
        lowered_query = query.lower()
        filtered = [
            message for message in filtered if lowered_query in _message_search_blob(message)
        ]
    from_filter = coerce_optional_trimmed_str(arguments.get("from"))
    if from_filter is not None:
        lowered_from = from_filter.lower()
        filtered = [
            message for message in filtered if lowered_from in _address_blob(message.get("from"))
        ]
    to_filter = coerce_optional_trimmed_str(arguments.get("to"))
    if to_filter is not None:
        lowered_to = to_filter.lower()
        filtered = [
            message for message in filtered if lowered_to in _address_blob(message.get("to"))
        ]
    subject_filter = coerce_optional_trimmed_str(arguments.get("subject"))
    if subject_filter is not None:
        lowered_subject = subject_filter.lower()
        filtered = [
            message
            for message in filtered
            if lowered_subject in str(message.get("subject") or "").lower()
        ]
    since_ms = _optional_int(arguments.get("since_ms"))
    if since_ms is not None:
        filtered = [
            message
            for message in filtered
            if (received_at_ms := _message_received_at_ms(message)) is not None
            and received_at_ms >= since_ms
        ]
    before_ms = _optional_int(arguments.get("before_ms"))
    if before_ms is not None:
        filtered = [
            message
            for message in filtered
            if (received_at_ms := _message_received_at_ms(message)) is not None
            and received_at_ms < before_ms
        ]
    for boolean_key in ("unread", "flagged", "has_attachments"):
        raw_value = arguments.get(boolean_key)
        if isinstance(raw_value, bool):
            filtered = [message for message in filtered if message.get(boolean_key) is raw_value]
    return filtered


def build_cache_coverage(messages: list[JSONDict], config: ConfigProtocol) -> JSONDict:
    received_values = [
        received_at_ms
        for message in messages
        if (received_at_ms := _message_received_at_ms(message)) is not None
    ]
    max_age_days = int(config.get_int("INTEGRATIONS.MAIL.SYNC.HISTORY.MAX_AGE_DAYS"))
    max_messages_per_folder = int(
        config.get_int("INTEGRATIONS.MAIL.SYNC.HISTORY.MAX_MESSAGES_PER_FOLDER"),
    )
    return {
        "oldest_received_at_ms": min(received_values) if received_values else None,
        "newest_received_at_ms": max(received_values) if received_values else None,
        "is_history_limited": len(messages) >= max_messages_per_folder,
        "history_policy": {
            "max_age_days": max_age_days,
            "max_messages_per_folder": max_messages_per_folder,
        },
    }


def _message_search_blob(message: JSONDict) -> str:
    fragments: list[str] = []
    for key in ("subject", "snippet"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            fragments.append(value.strip().lower())
    for key in ("from", "to", "cc", "bcc"):
        fragments.append(_address_blob(message.get(key)))
    return "\n".join(fragments)


def _address_blob(value: JSONValue) -> str:
    if not isinstance(value, list):
        return ""
    fragments: list[str] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        for subkey in ("email", "name"):
            subvalue = entry.get(subkey)
            if isinstance(subvalue, str) and subvalue.strip():
                fragments.append(subvalue.strip().lower())
    return "\n".join(fragments)


def _optional_int(value: JSONValue | None) -> int | None:
    if not is_strict_int(value):
        return None
    return int(value)


def _message_received_at_ms(message: JSONDict) -> int | None:
    received_at_ms_value = message.get("received_at_ms")
    if isinstance(received_at_ms_value, int):
        return received_at_ms_value
    return None
