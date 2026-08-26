"""SoAI - Mail IMAP remote search sync [backend/features/mail/imap_remote_search_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.mail.imap_mailboxes import read_imap_uidvalidity, select_imap_mailbox
from features.mail.imap_message_fetch import (
    fetch_imap_message_payloads,
    normalize_imap_response_data,
    parse_imap_uid_sequence,
)
from features.mail.imap_session import open_imap_connection

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = ("run_imap_remote_search_sync",)


def run_imap_remote_search_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    folder_mailboxes: list[str],
    search_criteria: tuple[str, ...],
    limit: int,
    snippet_max_chars: int,
) -> list[JSONDict]:
    matched: list[JSONDict] = []
    with open_imap_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        for mailbox in folder_mailboxes:
            select_imap_mailbox(connection, mailbox)
            uidvalidity = read_imap_uidvalidity(connection)
            status, search_data = connection.uid("search", *search_criteria)
            if status != "OK":
                continue
            normalized_search_data = normalize_imap_response_data(search_data)
            matched_uids = parse_imap_uid_sequence(normalized_search_data)
            matched.extend(
                fetch_imap_message_payloads(
                    connection=connection,
                    runtime_state=runtime_state,
                    remote_mailbox=mailbox,
                    uidvalidity=uidvalidity,
                    uids=matched_uids[-limit:],
                    snippet_max_chars=snippet_max_chars,
                ),
            )
    matched.sort(
        key=_matched_payload_sort_key,
        reverse=True,
    )
    return matched[:limit]


def _matched_payload_sort_key(item: JSONDict) -> tuple[int, str]:
    message_value = item.get("message")
    message = message_value if isinstance(message_value, dict) else {}
    received_at_ms_value = message.get("received_at_ms")
    received_at_ms = received_at_ms_value if isinstance(received_at_ms_value, int) else 0
    rfc822_message_id_value = message.get("rfc822_message_id")
    rfc822_message_id = rfc822_message_id_value if isinstance(rfc822_message_id_value, str) else ""
    return received_at_ms, rfc822_message_id
