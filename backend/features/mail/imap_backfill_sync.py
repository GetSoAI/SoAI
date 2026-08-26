"""SoAI - Mail IMAP backfill sync [backend/features/mail/imap_backfill_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.timing.formatting import timestamp_ms_to_utc_format
from features.mail.imap_mailboxes import (
    open_selected_imap_connection,
    read_imap_uidvalidity,
)
from features.mail.imap_message_fetch import (
    fetch_imap_message_payloads,
    normalize_imap_response_data,
    parse_imap_uid_sequence,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = ("run_imap_backfill_batch_sync",)


def run_imap_backfill_batch_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    remote_mailbox: str,
    batch_limit: int,
    end_index_exclusive: int | None,
    anchor_uid: int | None,
    before_ms: int | None,
    snippet_max_chars: int,
) -> JSONDict:
    with open_selected_imap_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
        remote_mailbox=remote_mailbox,
    ) as connection:
        uidvalidity = read_imap_uidvalidity(connection)
        search_criteria = _build_backfill_search_criteria(before_ms=before_ms)
        status, search_data = connection.uid("search", *search_criteria)
        if status != "OK":
            raise ValidationError("IMAP SEARCH failed during backfill.")
        if not isinstance(search_data, list):
            raise ValidationError("IMAP SEARCH payload is invalid.")
        normalized_search_data = normalize_imap_response_data(search_data)
        matched_uids = parse_imap_uid_sequence(normalized_search_data)
        resolved_end_index = len(matched_uids)
        if end_index_exclusive is not None:
            resolved_end_index = max(0, min(end_index_exclusive, len(matched_uids)))
        elif anchor_uid is not None and anchor_uid in matched_uids:
            resolved_end_index = matched_uids.index(anchor_uid)
        start_index = max(0, resolved_end_index - max(batch_limit, 1))
        selected_uids = matched_uids[start_index:resolved_end_index]
        uids_to_fetch = selected_uids
        payloads = fetch_imap_message_payloads(
            snippet_max_chars=snippet_max_chars,
            uids=uids_to_fetch,
            uidvalidity=uidvalidity,
            remote_mailbox=remote_mailbox,
            runtime_state=runtime_state,
            connection=connection,
        )
    return {
        "messages": payloads,
        "uidvalidity": uidvalidity,
        "next_end_index": start_index,
        "has_more": start_index > 0,
        "total_count": len(matched_uids),
    }


def _build_backfill_search_criteria(*, before_ms: int | None) -> tuple[str, ...]:
    if before_ms is None:
        return ("ALL",)
    return ("BEFORE", timestamp_ms_to_utc_format(before_ms, "%d-%b-%Y"))
