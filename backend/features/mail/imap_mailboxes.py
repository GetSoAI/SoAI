"""SoAI - Mail IMAP mailbox metadata helpers [backend/features/mail/imap_mailboxes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import imaplib
import re
from collections.abc import Generator
from contextlib import contextmanager
from datetime import timedelta
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.timing.formatting import utc_now
from features.mail.imap_session import open_imap_connection

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.imap_session import IMAPConnection
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = (
    "build_history_search_criteria",
    "list_imap_mailboxes",
    "open_selected_imap_connection",
    "read_imap_mailbox_status",
    "read_imap_uidvalidity",
    "select_imap_mailbox",
    "select_sync_mailboxes",
)


@contextmanager
def open_selected_imap_connection(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    remote_mailbox: str,
) -> Generator[IMAPConnection]:
    with open_imap_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        select_imap_mailbox(connection, remote_mailbox)
        yield connection


def list_imap_mailboxes(connection: imaplib.IMAP4) -> list[JSONDict]:
    status, raw_data = connection.list()
    if status != "OK" or not isinstance(raw_data, list):
        raise ValidationError("IMAP LIST failed.")
    mailboxes: list[JSONDict] = []
    for item in raw_data:
        if not isinstance(item, bytes):
            continue
        parsed = _parse_list_item(item)
        if parsed is not None:
            mailboxes.append(parsed)
    return mailboxes


def select_sync_mailboxes(
    *,
    mailboxes: list[JSONDict],
    target_remote_mailbox: str | None,
    include_special_use: bool,
    include_names: list[str],
    exclude_names: list[str],
) -> list[JSONDict]:
    include_names_lc = {item.strip().lower() for item in include_names if item.strip()}
    exclude_names_lc = {item.strip().lower() for item in exclude_names if item.strip()}
    selected: list[JSONDict] = []
    for mailbox in mailboxes:
        remote_mailbox = str(mailbox["remote_mailbox"]).strip()
        if target_remote_mailbox is not None and remote_mailbox != target_remote_mailbox:
            continue
        name_lc = remote_mailbox.lower()
        if name_lc in exclude_names_lc:
            continue
        special_use_value = mailbox.get("special_use")
        special_use = special_use_value if isinstance(special_use_value, str) else None
        if target_remote_mailbox is None:
            if name_lc == "inbox":
                selected.append(mailbox)
                continue
            if include_special_use and special_use is not None:
                selected.append(mailbox)
                continue
            if name_lc in include_names_lc:
                selected.append(mailbox)
                continue
            continue
        selected.append(mailbox)
    if target_remote_mailbox is not None and not selected:
        raise ValidationError("Requested remote mailbox was not found on the IMAP server.")
    if target_remote_mailbox is None and not selected:
        inbox_matches = [
            mailbox for mailbox in mailboxes if str(mailbox["remote_mailbox"]).lower() == "inbox"
        ]
        if inbox_matches:
            return inbox_matches
    return selected


def select_imap_mailbox(connection: imaplib.IMAP4, remote_mailbox: str) -> None:
    status, _data = connection.select(f'"{remote_mailbox}"', readonly=True)
    if status != "OK":
        raise ValidationError(f"Unable to open IMAP mailbox '{remote_mailbox}'.")


def read_imap_uidvalidity(connection: imaplib.IMAP4) -> int:
    response = connection.response("UIDVALIDITY")
    if not isinstance(response, tuple) or len(response) != 2 or not isinstance(response[1], list):
        raise StateError("IMAP mailbox UIDVALIDITY response is invalid.")
    for item in response[1]:
        if isinstance(item, bytes) and item.isdigit():
            return int(item)
    raise StateError("IMAP mailbox UIDVALIDITY is missing.")


def read_imap_mailbox_status(
    connection: imaplib.IMAP4,
    remote_mailbox: str,
) -> tuple[int, int]:
    status, data = connection.status(f'"{remote_mailbox}"', "(MESSAGES UNSEEN)")
    if status != "OK" or not isinstance(data, list):
        return (0, 0)
    messages = 0
    unseen = 0
    for item in data:
        if not isinstance(item, bytes):
            continue
        for key, value in re.findall(rb"(MESSAGES|UNSEEN)\s+(\d+)", item):
            normalized_key = key.decode("ascii", errors="replace")
            if normalized_key == "MESSAGES":
                messages = int(value)
            elif normalized_key == "UNSEEN":
                unseen = int(value)
    return messages, unseen


def build_history_search_criteria(history_max_age_days: int) -> tuple[str, ...]:
    if history_max_age_days <= 0:
        return ("ALL",)
    cutoff = utc_now() - timedelta(days=history_max_age_days)
    return ("SINCE", cutoff.strftime("%d-%b-%Y"))


def _parse_list_item(item: bytes) -> JSONDict | None:
    match = re.match(rb"^\((?P<flags>[^)]*)\)\s+\"(?P<delimiter>[^\"]*)\"\s+(?P<name>.+)$", item)
    if match is None:
        return None
    flags_text = match.group("flags").decode("utf-8", errors="replace")
    flags = [token for token in flags_text.split(" ") if token]
    raw_name = match.group("name").decode("utf-8", errors="replace").strip()
    remote_mailbox = (
        raw_name[1:-1] if raw_name.startswith('"') and raw_name.endswith('"') else raw_name
    )
    special_use = _resolve_special_use(flags=flags, remote_mailbox=remote_mailbox)
    return {
        "remote_mailbox": remote_mailbox,
        "name": remote_mailbox,
        "special_use": special_use,
        "subscribed": "\\Noselect" not in flags and "\\NonExistent" not in flags,
    }


def _resolve_special_use(*, flags: list[str], remote_mailbox: str) -> str | None:
    flag_map = {
        "\\Inbox": "inbox",
        "\\Sent": "sent",
        "\\Drafts": "drafts",
        "\\Trash": "trash",
        "\\Archive": "archive",
        "\\Junk": "junk",
        "\\Spam": "junk",
    }
    for flag in flags:
        if flag in flag_map:
            return flag_map[flag]
    normalized_remote_mailbox = remote_mailbox.lower()
    if normalized_remote_mailbox in {
        "inbox",
        "sent",
        "drafts",
        "trash",
        "archive",
        "junk",
        "spam",
    }:
        return {
            "inbox": "inbox",
            "sent": "sent",
            "drafts": "drafts",
            "trash": "trash",
            "archive": "archive",
            "junk": "junk",
            "spam": "junk",
        }[normalized_remote_mailbox]
    return None
