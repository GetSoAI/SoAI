"""SoAI - Mail IMAP read and sync helpers [backend/features/mail/imap_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import imaplib
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from features.mail.imap_backfill_sync import run_imap_backfill_batch_sync
from features.mail.imap_mailboxes import (
    build_history_search_criteria,
    list_imap_mailboxes,
    open_selected_imap_connection,
    read_imap_mailbox_status,
    read_imap_uidvalidity,
    select_imap_mailbox,
    select_sync_mailboxes,
)
from features.mail.imap_message_fetch import (
    fetch_imap_message_bytes_sync,
    fetch_imap_message_payloads,
    normalize_imap_response_data,
    parse_imap_uid_sequence,
)
from features.mail.imap_remote_search_sync import run_imap_remote_search_sync
from features.mail.imap_session import open_imap_connection

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = (
    "fetch_imap_message_bytes_for_account_sync",
    "run_imap_backfill_batch_sync",
    "run_imap_connectivity_check_sync",
    "run_imap_remote_search_sync",
    "run_imap_sync_snapshot_sync",
)


def run_imap_connectivity_check_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
) -> JSONDict:
    with open_imap_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        status, data = connection.list()
        if status != "OK":
            raise ValidationError("IMAP LIST failed during account test.")
    listed_count = 0
    if isinstance(data, list):
        listed_count = len([item for item in data if isinstance(item, bytes)])
    return {"status": "ok", "listed_mailboxes": listed_count}


def run_imap_sync_snapshot_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    history_max_age_days: int,
    max_messages_per_folder: int,
    target_remote_mailbox: str | None,
    include_special_use: bool,
    include_names: list[str],
    exclude_names: list[str],
    snippet_max_chars: int,
) -> JSONDict:
    with open_imap_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        mailboxes = list_imap_mailboxes(connection)
        selected_mailboxes = select_sync_mailboxes(
            mailboxes=mailboxes,
            target_remote_mailbox=target_remote_mailbox,
            include_special_use=include_special_use,
            include_names=include_names,
            exclude_names=exclude_names,
        )
        messages_by_mailbox: dict[str, list[JSONDict]] = {}
        selected_folders: list[JSONDict] = []
        listed_folders: list[JSONDict] = []
        selected_remote_mailboxes = {
            _require_mailbox_remote_mailbox(mailbox) for mailbox in selected_mailboxes
        }
        for mailbox in mailboxes:
            remote_mailbox = _require_mailbox_remote_mailbox(mailbox)
            if remote_mailbox in selected_remote_mailboxes:
                folder_payload, message_payloads = _sync_mailbox(
                    connection=connection,
                    runtime_state=runtime_state,
                    mailbox=mailbox,
                    history_max_age_days=history_max_age_days,
                    max_messages_per_folder=max_messages_per_folder,
                    snippet_max_chars=snippet_max_chars,
                )
                selected_folders.append(folder_payload)
                listed_folders.append(folder_payload)
                messages_by_mailbox[remote_mailbox] = message_payloads
                continue
            listed_folders.append(
                _read_mailbox_folder_payload(
                    connection=connection,
                    mailbox=mailbox,
                ),
            )
    return {
        "folders": selected_folders,
        "listed_folders": listed_folders,
        "messages_by_mailbox": messages_by_mailbox,
    }


def fetch_imap_message_bytes_for_account_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    remote_mailbox: str,
    uid: int,
) -> bytes:
    with open_selected_imap_connection(
        remote_mailbox=remote_mailbox,
        connect_host=connect_host,
        connect_timeout_sec=connect_timeout_sec,
        auth_payload=auth_payload,
        runtime_state=runtime_state,
    ) as connection:
        return fetch_imap_message_bytes_sync(connection=connection, uid=uid)


def _sync_mailbox(
    *,
    connection: imaplib.IMAP4,
    runtime_state: MailAccountRuntimeState,
    mailbox: JSONDict,
    history_max_age_days: int,
    max_messages_per_folder: int,
    snippet_max_chars: int,
) -> tuple[JSONDict, list[JSONDict]]:
    remote_mailbox = _require_mailbox_remote_mailbox(mailbox)
    select_imap_mailbox(connection, remote_mailbox)
    uidvalidity = read_imap_uidvalidity(connection)
    messages_count, unseen_count = read_imap_mailbox_status(connection, remote_mailbox)
    search_criteria = build_history_search_criteria(history_max_age_days)
    status, search_data = connection.uid("search", *search_criteria)
    if status != "OK":
        raise ValidationError("IMAP SEARCH failed during sync.")
    if not isinstance(search_data, list):
        raise ValidationError("IMAP SEARCH payload is invalid.")
    normalized_search_data = normalize_imap_response_data(search_data)
    matched_uids = parse_imap_uid_sequence(normalized_search_data)
    selected_uids = matched_uids[-max_messages_per_folder:]
    payloads = fetch_imap_message_payloads(
        connection=connection,
        runtime_state=runtime_state,
        remote_mailbox=remote_mailbox,
        uidvalidity=uidvalidity,
        uids=selected_uids,
        snippet_max_chars=snippet_max_chars,
    )
    folder_payload = _build_folder_payload(
        mailbox=mailbox,
        messages_count=messages_count,
        unseen_count=unseen_count,
    )
    return folder_payload, payloads


def _read_mailbox_folder_payload(
    *,
    connection: imaplib.IMAP4,
    mailbox: JSONDict,
) -> JSONDict:
    remote_mailbox = _require_mailbox_remote_mailbox(mailbox)
    messages_count, unseen_count = read_imap_mailbox_status(connection, remote_mailbox)
    return _build_folder_payload(
        mailbox=mailbox,
        messages_count=messages_count,
        unseen_count=unseen_count,
    )


def _build_folder_payload(
    *,
    mailbox: JSONDict,
    messages_count: int,
    unseen_count: int,
) -> JSONDict:
    remote_mailbox = _require_mailbox_remote_mailbox(mailbox)
    return {
        "remote_mailbox": remote_mailbox,
        "name": mailbox.get("name") if isinstance(mailbox.get("name"), str) else remote_mailbox,
        "special_use": (
            mailbox.get("special_use") if isinstance(mailbox.get("special_use"), str) else None
        ),
        "subscribed": mailbox.get("subscribed") is True,
        "unread_count": unseen_count,
        "message_count": messages_count,
    }


def _require_mailbox_remote_mailbox(mailbox: JSONDict) -> str:
    remote_mailbox_value = mailbox.get("remote_mailbox")
    remote_mailbox = remote_mailbox_value.strip() if isinstance(remote_mailbox_value, str) else ""
    if not remote_mailbox:
        raise ValidationError("IMAP mailbox remote_mailbox is invalid.")
    return remote_mailbox
