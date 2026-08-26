"""SoAI - Mail message transfer mutations [backend/features/mail/mail_message_transfer_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.errors.exceptions import StateError, ValidationError
from core.types.json import JSONDict
from features.mail.formatting import format_mail_message
from features.mail.imap_mutations import (
    copy_imap_message_sync,
    delete_imap_message_sync,
    move_imap_message_sync,
)
from features.mail.internal_protocols import MailRuntimeServiceProtocol
from features.mail.mail_cache_sync import sync_mail_account_cache
from features.mail.mail_folder_targets import resolve_special_folder
from features.mail.mail_message_context import (
    LoadedMailMessageContext,
    MailMessageDestination,
    require_message_uid,
    resolve_explicit_destination,
    resolve_restore_destination,
    sync_target_and_find_message,
)

if TYPE_CHECKING:
    from features.mail.transport_context import PreparedMailTransportContext

__all__ = (
    "copy_imap_message",
    "delete_imap_message",
    "move_imap_message",
    "resolve_archive_destination",
)


async def copy_imap_message(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    context: LoadedMailMessageContext,
    prepared: PreparedMailTransportContext,
    destination_folder_id: str | None,
) -> JSONDict:
    destination = await resolve_explicit_destination(
        service,
        user_id=user_id,
        account_id=context.account_id,
        destination_folder_id=destination_folder_id,
    )
    if destination.folder_id == context.folder_id:
        return format_mail_message(context.message, protocol="imap")
    await run_bounded_blocking_call(
        service.mail_blocking_pool,
        partial(
            copy_imap_message_sync,
            runtime_state=prepared.runtime_state,
            auth_payload=prepared.auth_payload,
            connect_timeout_sec=prepared.connect_timeout_sec,
            connect_host=prepared.inbound_connect_host,
            remote_mailbox=context.remote_mailbox,
            uid=require_message_uid(context.message),
            destination_remote_mailbox=destination.remote_mailbox,
        ),
        timeout_sec=prepared.connect_timeout_sec
        + float(service.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
    )
    copied_message = await sync_target_and_find_message(
        service,
        user_id=user_id,
        account_id=context.account_id,
        remote_mailbox=destination.remote_mailbox,
        folder_id=destination.folder_id,
        message=context.message,
    )
    if copied_message is None:
        raise StateError("Copied IMAP message was not found after target sync.")
    formatted = format_mail_message(copied_message, protocol="imap")
    formatted["copied"] = True
    return formatted


async def move_imap_message(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    context: LoadedMailMessageContext,
    prepared: PreparedMailTransportContext,
    destination_remote_mailbox: str,
    destination_folder_id: str | None,
    deleted_original_folder_id: str | None,
    deleted: bool,
) -> JSONDict:
    if destination_remote_mailbox == context.remote_mailbox:
        current = format_mail_message(context.message, protocol="imap")
        if deleted_original_folder_id is not None:
            current["deleted_original_folder_id"] = deleted_original_folder_id
        if deleted:
            current["deleted"] = True
        return current
    await run_bounded_blocking_call(
        service.mail_blocking_pool,
        partial(
            move_imap_message_sync,
            runtime_state=prepared.runtime_state,
            auth_payload=prepared.auth_payload,
            connect_timeout_sec=prepared.connect_timeout_sec,
            connect_host=prepared.inbound_connect_host,
            remote_mailbox=context.remote_mailbox,
            uid=require_message_uid(context.message),
            destination_remote_mailbox=destination_remote_mailbox,
        ),
        timeout_sec=prepared.connect_timeout_sec
        + float(service.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
    )
    moved_message = await sync_target_and_find_message(
        service,
        user_id=user_id,
        account_id=context.account_id,
        remote_mailbox=destination_remote_mailbox,
        folder_id=destination_folder_id,
        message=context.message,
    )
    context_message_id = str(context.message["id"])
    await service.database_mail.delete_message(
        user_id=user_id,
        message_id=context_message_id,
    )
    await sync_mail_account_cache(
        service,
        user_id=user_id,
        account_id=context.account_id,
        folder_id=context.folder_id,
    )
    if moved_message is None:
        raise StateError("Moved IMAP message was not found after target sync.")
    message_id_value = moved_message.get("id")
    message_id = message_id_value if isinstance(message_id_value, str) else ""
    if message_id and deleted_original_folder_id is not None:
        updated = await service.database_mail.update_message(
            user_id=user_id,
            message_id=message_id,
            updates={"deleted_original_folder_id": deleted_original_folder_id},
        )
        if updated is not None:
            moved_message = updated
    elif message_id:
        updated = await service.database_mail.update_message(
            user_id=user_id,
            message_id=message_id,
            updates={"deleted_original_folder_id": None},
        )
        if updated is not None:
            moved_message = updated
    formatted = format_mail_message(moved_message, protocol="imap")
    if deleted:
        formatted["deleted"] = True
    return formatted


async def delete_imap_message(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    context: LoadedMailMessageContext,
    prepared: PreparedMailTransportContext,
) -> JSONDict:
    current_special_use = context.folder.get("special_use")
    trash_folder_id, trash_remote_mailbox = await resolve_special_folder(
        database_mail=service.database_mail,
        user_id=user_id,
        account_id=context.account_id,
        runtime_state=prepared.runtime_state,
        special_use="trash",
    )
    if current_special_use != "trash" and trash_remote_mailbox is not None:
        return await move_imap_message(
            service,
            user_id=user_id,
            context=context,
            prepared=prepared,
            destination_remote_mailbox=trash_remote_mailbox,
            destination_folder_id=trash_folder_id,
            deleted_original_folder_id=context.folder_id,
            deleted=True,
        )
    await run_bounded_blocking_call(
        service.mail_blocking_pool,
        partial(
            delete_imap_message_sync,
            runtime_state=prepared.runtime_state,
            auth_payload=prepared.auth_payload,
            connect_timeout_sec=prepared.connect_timeout_sec,
            connect_host=prepared.inbound_connect_host,
            remote_mailbox=context.remote_mailbox,
            uid=require_message_uid(context.message),
        ),
        timeout_sec=prepared.connect_timeout_sec
        + float(service.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
    )
    deleted_snapshot: JSONDict = format_mail_message(context.message, protocol="imap")
    deleted_snapshot["deleted"] = True
    message_id = str(context.message["id"])
    await service.database_mail.delete_message(
        message_id=message_id,
        user_id=user_id,
    )
    cache_account_id = context.account_id
    cache_folder_id = context.folder_id
    await sync_mail_account_cache(
        service,
        user_id=user_id,
        folder_id=cache_folder_id,
        account_id=cache_account_id,
    )
    return deleted_snapshot


async def resolve_archive_destination(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    context: LoadedMailMessageContext,
    prepared: PreparedMailTransportContext,
    special_use: str,
) -> MailMessageDestination:
    if special_use == "restore":
        return await resolve_restore_destination(
            service,
            user_id=user_id,
            context=context,
            prepared=prepared,
        )
    folder_id_value, remote_mailbox = await resolve_special_folder(
        database_mail=service.database_mail,
        user_id=user_id,
        account_id=context.account_id,
        runtime_state=prepared.runtime_state,
        special_use=special_use,
    )
    if remote_mailbox is None:
        label = "Archive" if special_use == "archive" else "Inbox"
        raise ValidationError(f"{label} action requires a configured {label} folder.")
    return MailMessageDestination(
        folder_id=folder_id_value,
        remote_mailbox=remote_mailbox,
    )
