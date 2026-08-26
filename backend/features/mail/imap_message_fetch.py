"""SoAI - Mail IMAP message fetch helpers [backend/features/mail/imap_message_fetch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import imaplib
import re
from datetime import datetime
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.timing.datetime_conversion import datetime_to_epoch_ms
from features.mail.message_parsing import parse_message_bytes

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = (
    "fetch_imap_message_bytes_sync",
    "fetch_imap_message_payload",
    "fetch_imap_message_payloads",
    "normalize_imap_response_data",
    "parse_imap_uid_sequence",
)

_FETCH_QUERY = "(UID FLAGS INTERNALDATE RFC822)"
_FETCH_BATCH_SIZE = 100


def fetch_imap_message_payload(
    *,
    connection: imaplib.IMAP4,
    runtime_state: MailAccountRuntimeState,
    remote_mailbox: str,
    uidvalidity: int,
    uid: int,
    snippet_max_chars: int,
) -> JSONDict:
    payloads = fetch_imap_message_payloads(
        connection=connection,
        runtime_state=runtime_state,
        remote_mailbox=remote_mailbox,
        uidvalidity=uidvalidity,
        uids=[uid],
        snippet_max_chars=snippet_max_chars,
    )
    if len(payloads) != 1:
        raise StateError("IMAP FETCH returned an invalid message count.")
    return payloads[0]


def fetch_imap_message_payloads(
    *,
    connection: imaplib.IMAP4,
    runtime_state: MailAccountRuntimeState,
    remote_mailbox: str,
    uidvalidity: int,
    uids: list[int],
    snippet_max_chars: int,
) -> list[JSONDict]:
    if not uids:
        return []
    payloads_by_uid: dict[int, JSONDict] = {}
    for uid_batch in _iter_uid_batches(uids, _FETCH_BATCH_SIZE):
        uid_batch_set = set(uid_batch)
        status, fetch_data = connection.uid(
            "fetch",
            ",".join(str(uid) for uid in uid_batch),
            _FETCH_QUERY,
        )
        if status != "OK":
            raise ValidationError("IMAP FETCH failed while loading messages.")
        normalized_fetch_data = normalize_imap_response_data(fetch_data)
        for header_bytes, message_bytes in _iter_fetch_tuples(normalized_fetch_data):
            response_uid = _extract_uid(header_bytes)
            if response_uid not in uid_batch_set:
                raise StateError("IMAP FETCH returned an unexpected UID.")
            if response_uid in payloads_by_uid:
                raise StateError("IMAP FETCH returned a duplicate UID.")
            payloads_by_uid[response_uid] = _build_message_payload(
                runtime_state=runtime_state,
                remote_mailbox=remote_mailbox,
                uidvalidity=uidvalidity,
                uid=response_uid,
                snippet_max_chars=snippet_max_chars,
                header_bytes=header_bytes,
                message_bytes=message_bytes,
            )
        missing_uids = [uid for uid in uid_batch if uid not in payloads_by_uid]
        if missing_uids:
            raise StateError("IMAP FETCH returned incomplete message data.")
    return [payloads_by_uid[uid] for uid in uids]


def fetch_imap_message_bytes_sync(
    *,
    connection: imaplib.IMAP4,
    uid: int,
) -> bytes:
    status, fetch_data = connection.uid("fetch", str(uid), "(UID RFC822)")
    if status != "OK":
        raise ValidationError("IMAP fetch failed.")
    normalized_fetch_data = normalize_imap_response_data(fetch_data)
    message_bytes = _extract_fetch_message_bytes(normalized_fetch_data)
    if message_bytes is None:
        raise StateError("IMAP fetch returned no message bytes.")
    return message_bytes


def normalize_imap_response_data(
    data: list[bytes | tuple[bytes, bytes] | None],
) -> list[bytes | tuple[bytes, bytes] | None]:
    normalized_data: list[bytes | tuple[bytes, bytes] | None] = []
    for item in data:
        if isinstance(item, bytes) or item is None:
            normalized_data.append(item)
            continue
        if isinstance(item, tuple) and len(item) == 2:
            first_item = item[0]
            second_item = item[1]
            if isinstance(first_item, bytes) and isinstance(second_item, bytes):
                normalized_data.append((first_item, second_item))
    return normalized_data


def parse_imap_uid_sequence(data: list[bytes | tuple[bytes, bytes] | None]) -> list[int]:
    if not data:
        return []
    first = data[0]
    if not isinstance(first, bytes):
        return []
    return [int(token) for token in first.split() if token.isdigit()]


def _build_message_payload(
    *,
    runtime_state: MailAccountRuntimeState,
    remote_mailbox: str,
    uidvalidity: int,
    uid: int,
    snippet_max_chars: int,
    header_bytes: bytes,
    message_bytes: bytes,
) -> JSONDict:
    flags = _extract_flags(header_bytes)
    received_at_ms = _extract_internaldate_epoch_ms(header_bytes)
    return parse_message_bytes(
        message_bytes=message_bytes,
        remote_mailbox=remote_mailbox,
        uidvalidity=uidvalidity,
        uid=uid,
        uidl=None,
        received_at_ms=received_at_ms,
        unread="\\Seen" not in flags,
        flagged="\\Flagged" in flags,
        attachment_identity_key=f"imap:{runtime_state.account_id}:{remote_mailbox}:{uidvalidity}:{uid}",
        snippet_max_chars=snippet_max_chars,
    )


def _extract_fetch_message_bytes(data: list[bytes | tuple[bytes, bytes] | None]) -> bytes | None:
    for item in data:
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], bytes):
            return item[1]
    return None


def _iter_fetch_tuples(
    data: list[bytes | tuple[bytes, bytes] | None],
) -> list[tuple[bytes, bytes]]:
    fetch_tuples: list[tuple[bytes, bytes]] = []
    for item in data:
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], bytes)
            and isinstance(item[1], bytes)
        ):
            fetch_tuples.append((item[0], item[1]))
    if not fetch_tuples:
        raise StateError("IMAP FETCH returned no message payload.")
    return fetch_tuples


def _extract_flags(header_bytes: bytes) -> set[str]:
    match = re.search(rb"FLAGS\s+\((?P<flags>[^)]*)\)", header_bytes)
    if match is None:
        return set()
    return {
        token
        for token in match.group("flags").decode("utf-8", errors="replace").split(" ")
        if token
    }


def _extract_uid(header_bytes: bytes) -> int:
    match = re.search(rb"UID\s+(?P<value>\d+)", header_bytes)
    if match is None:
        raise StateError("IMAP FETCH returned no UID.")
    return int(match.group("value"))


def _extract_internaldate_epoch_ms(header_bytes: bytes) -> int:
    match = re.search(rb'INTERNALDATE\s+"(?P<value>[^"]+)"', header_bytes)
    if match is None:
        return 0
    text_value = match.group("value").decode("utf-8", errors="replace")
    parsed = datetime.strptime(text_value, "%d-%b-%Y %H:%M:%S %z")
    return datetime_to_epoch_ms(parsed)


def _iter_uid_batches(uids: list[int], batch_size: int) -> list[list[int]]:
    if batch_size < 1:
        raise ValidationError("IMAP batch_size is invalid.")
    return [uids[index : index + batch_size] for index in range(0, len(uids), batch_size)]
