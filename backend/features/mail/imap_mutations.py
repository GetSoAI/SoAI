"""SoAI - Mail IMAP mutation helpers [backend/features/mail/imap_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import imaplib
from email import policy
from email.message import EmailMessage
from typing import TYPE_CHECKING

from features.mail.imap_command_primitives import quote_imap_mailbox, require_imap_ok
from features.mail.imap_mailboxes import open_selected_imap_connection
from features.mail.imap_session import open_imap_connection

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.imap_session import IMAPConnection
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = (
    "append_imap_message_sync",
    "copy_imap_message_sync",
    "delete_imap_message_sync",
    "move_imap_message_sync",
    "set_imap_message_flags_sync",
)


def set_imap_message_flags_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    remote_mailbox: str,
    uid: int,
    mode: str,
    flags: tuple[str, ...],
) -> None:
    with open_selected_imap_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        remote_mailbox=remote_mailbox,
        connect_host=connect_host,
        connect_timeout_sec=connect_timeout_sec,
    ) as selected_connection:
        _store_flags(connection=selected_connection, uid=uid, mode=mode, flags=flags)


def copy_imap_message_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    remote_mailbox: str,
    uid: int,
    destination_remote_mailbox: str,
) -> None:
    with open_selected_imap_connection(
        remote_mailbox=remote_mailbox,
        runtime_state=runtime_state,
        connect_host=connect_host,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
    ) as connection:
        status, _data = connection.uid(
            "COPY",
            str(uid),
            quote_imap_mailbox(destination_remote_mailbox),
        )
        require_imap_ok(status, "IMAP COPY failed.")


def move_imap_message_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    remote_mailbox: str,
    uid: int,
    destination_remote_mailbox: str,
) -> None:
    with open_selected_imap_connection(
        remote_mailbox=remote_mailbox,
        connect_host=connect_host,
        runtime_state=runtime_state,
        connect_timeout_sec=connect_timeout_sec,
        auth_payload=auth_payload,
    ) as connection:
        capabilities = _capabilities(connection)
        if "MOVE" in capabilities:
            status, _data = connection.uid(
                "MOVE",
                str(uid),
                quote_imap_mailbox(destination_remote_mailbox),
            )
            require_imap_ok(status, "IMAP MOVE failed.")
            return
        status, _data = connection.uid(
            "COPY",
            str(uid),
            quote_imap_mailbox(destination_remote_mailbox),
        )
        require_imap_ok(status, "IMAP COPY failed during move.")
        _store_flags(connection=connection, uid=uid, mode="+FLAGS.SILENT", flags=("\\Deleted",))
        _expunge_deleted_message(
            connection=connection,
            capabilities=capabilities,
            uid=uid,
            uid_expunge_failure_message="IMAP UID EXPUNGE failed during move.",
            expunge_failure_message="IMAP EXPUNGE failed during move.",
        )


def append_imap_message_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    remote_mailbox: str,
    message: EmailMessage,
    draft: bool,
) -> None:
    flags = "(\\Draft)" if draft else ""
    with open_imap_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        append_result = connection.append(
            quote_imap_mailbox(remote_mailbox),
            flags,
            "",
            message.as_bytes(policy=policy.SMTP),
        )
        if isinstance(append_result, tuple):
            status = append_result[0]
        else:
            status = append_result
        require_imap_ok(status, "IMAP APPEND failed.")


def delete_imap_message_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    remote_mailbox: str,
    uid: int,
) -> None:
    with open_selected_imap_connection(
        remote_mailbox=remote_mailbox,
        connect_timeout_sec=connect_timeout_sec,
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_host=connect_host,
    ) as selected_connection:
        capabilities = _capabilities(selected_connection)
        _store_flags(
            connection=selected_connection,
            uid=uid,
            mode="+FLAGS.SILENT",
            flags=("\\Deleted",),
        )
        _expunge_deleted_message(
            connection=selected_connection,
            capabilities=capabilities,
            uid=uid,
            uid_expunge_failure_message="IMAP UID EXPUNGE failed during delete.",
            expunge_failure_message="IMAP EXPUNGE failed during delete.",
        )


def _capabilities(connection: imaplib.IMAP4) -> set[str]:
    values = connection.capabilities
    capabilities: set[str] = set()
    for item in values:
        if isinstance(item, bytes):
            capabilities.add(item.decode("ascii", errors="replace").upper())
        elif isinstance(item, str):
            capabilities.add(item.strip().upper())
    return capabilities


def _store_flags(
    *,
    connection: imaplib.IMAP4,
    uid: int,
    mode: str,
    flags: tuple[str, ...],
) -> None:
    normalized_flags = " ".join(flags)
    status, _data = connection.uid("STORE", str(uid), mode, f"({normalized_flags})")
    require_imap_ok(status, "IMAP STORE failed.")


def _expunge_deleted_message(
    *,
    connection: IMAPConnection,
    capabilities: set[str],
    uid: int,
    uid_expunge_failure_message: str,
    expunge_failure_message: str,
) -> None:
    if "UIDPLUS" in capabilities:
        status, _uid_data = connection.uid("EXPUNGE", str(uid))
        require_imap_ok(status, uid_expunge_failure_message)
        return
    status, _close_data = connection.close()
    require_imap_ok(status, expunge_failure_message)
