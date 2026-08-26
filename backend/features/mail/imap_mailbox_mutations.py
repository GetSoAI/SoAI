"""SoAI - Mail IMAP mailbox mutation helpers [backend/features/mail/imap_mailbox_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.mail.imap_command_primitives import quote_imap_mailbox, require_imap_ok
from features.mail.imap_session import open_imap_connection

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = (
    "create_imap_mailbox_sync",
    "delete_imap_mailbox_sync",
    "rename_imap_mailbox_sync",
    "set_imap_subscription_sync",
)


def create_imap_mailbox_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    folder_name: str,
) -> None:
    with open_imap_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        status, _data = connection.create(quote_imap_mailbox(folder_name))
        require_imap_ok(status, "IMAP CREATE failed.")


def rename_imap_mailbox_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    remote_mailbox: str,
    new_remote_mailbox: str,
) -> None:
    with open_imap_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        status, _data = connection.rename(
            quote_imap_mailbox(remote_mailbox),
            quote_imap_mailbox(new_remote_mailbox),
        )
        require_imap_ok(status, "IMAP RENAME failed.")


def delete_imap_mailbox_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    remote_mailbox: str,
) -> None:
    with open_imap_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        status, _data = connection.delete(quote_imap_mailbox(remote_mailbox))
        require_imap_ok(status, "IMAP DELETE failed.")


def set_imap_subscription_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    remote_mailbox: str,
    subscribed: bool,
) -> None:
    with open_imap_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        if subscribed:
            status, _data = connection.subscribe(quote_imap_mailbox(remote_mailbox))
            require_imap_ok(status, "IMAP SUBSCRIBE failed.")
            return
        status, _data = connection.unsubscribe(quote_imap_mailbox(remote_mailbox))
        require_imap_ok(status, "IMAP UNSUBSCRIBE failed.")
