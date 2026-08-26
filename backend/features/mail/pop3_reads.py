"""SoAI - Mail POP3 read and sync helpers [backend/features/mail/pop3_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.mail.pop3_message_fetch import (
    fetch_pop3_message_bytes_sync,
    fetch_pop3_payload,
)
from features.mail.pop3_session import (
    open_pop3_connection_context,
    open_pop3_uidl_listing_context,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = (
    "fetch_pop3_message_bytes_sync",
    "run_pop3_backfill_batch_reverse_sync",
    "run_pop3_backfill_batch_sync",
    "run_pop3_connectivity_check_sync",
    "run_pop3_sync_snapshot_sync",
)

_POP3_INBOX = "INBOX"


def run_pop3_connectivity_check_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
) -> JSONDict:
    with open_pop3_connection_context(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        message_count, _size_bytes = connection.stat()
    return {"status": "ok", "message_count": int(message_count)}


def run_pop3_sync_snapshot_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    max_messages_per_folder: int,
    snippet_max_chars: int,
) -> JSONDict:
    with open_pop3_uidl_listing_context(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as listing:
        total_count = len(listing.entries)
        selected = listing.entries[-max_messages_per_folder:]
        messages = [
            fetch_pop3_payload(
                connection=listing.connection,
                runtime_state=runtime_state,
                message_number=message_number,
                uidl=uidl,
                snippet_max_chars=snippet_max_chars,
            )
            for message_number, uidl in selected
        ]
    return {
        "folder": {
            "remote_mailbox": _POP3_INBOX,
            "name": _POP3_INBOX,
            "special_use": "inbox",
            "subscribed": True,
            "unread_count": 0,
            "message_count": total_count,
        },
        "messages": messages,
        "total_count": total_count,
    }


def run_pop3_backfill_batch_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    start_index: int,
    batch_limit: int,
    snippet_max_chars: int,
) -> JSONDict:
    with open_pop3_uidl_listing_context(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as listing:
        total_count = len(listing.entries)
        normalized_start = max(start_index, 0)
        selected = listing.entries[normalized_start : normalized_start + batch_limit]
        messages = [
            fetch_pop3_payload(
                connection=listing.connection,
                runtime_state=runtime_state,
                message_number=message_number,
                uidl=uidl,
                snippet_max_chars=snippet_max_chars,
            )
            for message_number, uidl in selected
        ]
    return {
        "messages": messages,
        "total_count": total_count,
        "next_start_index": normalized_start + len(selected),
        "has_more": (normalized_start + len(selected)) < total_count,
    }


def run_pop3_backfill_batch_reverse_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    batch_limit: int,
    end_index_exclusive: int | None,
    anchor_uidl: str | None,
    snippet_max_chars: int,
) -> JSONDict:
    with open_pop3_uidl_listing_context(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as listing:
        total_count = len(listing.entries)
        resolved_end_index = total_count
        if end_index_exclusive is not None:
            resolved_end_index = max(0, min(end_index_exclusive, total_count))
        elif anchor_uidl is not None:
            for index, (_message_number, entry_uidl) in enumerate(listing.entries):
                if entry_uidl == anchor_uidl:
                    resolved_end_index = index
                    break
        start_index = max(0, resolved_end_index - max(batch_limit, 1))
        selected = listing.entries[start_index:resolved_end_index]
        messages = [
            fetch_pop3_payload(
                connection=listing.connection,
                runtime_state=runtime_state,
                message_number=message_number,
                uidl=uidl,
                snippet_max_chars=snippet_max_chars,
            )
            for message_number, uidl in selected
        ]
    return {
        "messages": messages,
        "total_count": total_count,
        "next_end_index": start_index,
        "has_more": start_index > 0,
    }
