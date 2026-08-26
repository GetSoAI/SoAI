"""SoAI - Mail message mutation context [backend/features/mail/mail_message_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.types.json import JSONDict
from core.validation.strings import coerce_trimmed_str_or_empty
from features.mail.internal_protocols import MailRuntimeServiceProtocol
from features.mail.mail_cache_sync import sync_mail_account_cache
from features.mail.mail_folder_targets import resolve_special_folder
from features.mail.mail_message_lookup import find_message_id_by_message_signature
from features.mail.mail_record_context import (
    load_folder_context,
    require_folder_account_id,
    require_remote_mailbox,
)

if TYPE_CHECKING:
    from features.mail.transport_context import PreparedMailTransportContext

__all__ = (
    "LoadedMailMessageContext",
    "load_message_context",
    "require_message_uid",
    "resolve_explicit_destination",
    "resolve_restore_destination",
    "sync_target_and_find_message",
)


@dataclass(frozen=True, slots=True)
class LoadedMailMessageContext:
    message: JSONDict
    folder: JSONDict
    account: JSONDict
    folder_id: str
    account_id: str
    protocol: str
    remote_mailbox: str


@dataclass(frozen=True, slots=True)
class MailMessageDestination:
    folder_id: str | None
    remote_mailbox: str


async def load_message_context(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    message_id: str,
) -> LoadedMailMessageContext:
    message = await service.database_mail.get_message(user_id=user_id, message_id=message_id)
    if message is None:
        raise ValidationError("Mail message not found.")
    folder_id_value = message.get("folder_id")
    folder_id = folder_id_value.strip() if isinstance(folder_id_value, str) else ""
    if not folder_id:
        raise StateError("Mail message is missing its folder id.")
    folder_context = await load_folder_context(
        service.database_mail,
        user_id=user_id,
        folder_id=folder_id,
        missing_error=StateError,
        missing_message="Mail folder not found.",
    )
    remote_mailbox = (
        require_remote_mailbox(message, message="IMAP message is missing its remote mailbox.")
        if folder_context.protocol == "imap"
        else coerce_trimmed_str_or_empty(message.get("remote_mailbox"))
    )
    return LoadedMailMessageContext(
        message=message,
        folder=folder_context.folder,
        account=folder_context.account,
        folder_id=folder_id,
        account_id=folder_context.account_id,
        protocol=folder_context.protocol,
        remote_mailbox=remote_mailbox,
    )


async def resolve_explicit_destination(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    destination_folder_id: str | None,
) -> MailMessageDestination:
    if destination_folder_id is None:
        raise ValidationError("destination_folder_id is required for this action.")
    folder = await service.database_mail.get_folder(
        user_id=user_id,
        folder_id=destination_folder_id,
    )
    if folder is None:
        raise ValidationError("Destination mail folder not found.")
    folder_account_id = require_folder_account_id(folder)
    if folder_account_id != account_id:
        raise ValidationError("Destination mail folder belongs to another account.")
    remote_mailbox = require_remote_mailbox(
        folder,
        message="Destination mail folder is missing its remote mailbox.",
    )
    return MailMessageDestination(
        folder_id=destination_folder_id,
        remote_mailbox=remote_mailbox,
    )


async def resolve_restore_destination(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    context: LoadedMailMessageContext,
    prepared: PreparedMailTransportContext,
) -> MailMessageDestination:
    original_folder_id_value = context.message.get("deleted_original_folder_id")
    original_folder_id = (
        original_folder_id_value.strip() if isinstance(original_folder_id_value, str) else ""
    )
    if original_folder_id:
        return await resolve_explicit_destination(
            service,
            user_id=user_id,
            account_id=context.account_id,
            destination_folder_id=original_folder_id,
        )
    folder_id_value, remote_mailbox = await resolve_special_folder(
        database_mail=service.database_mail,
        user_id=user_id,
        account_id=context.account_id,
        runtime_state=prepared.runtime_state,
        special_use="inbox",
    )
    if remote_mailbox is None:
        raise ValidationError("Restore action requires a configured Inbox folder.")
    return MailMessageDestination(
        folder_id=folder_id_value,
        remote_mailbox=remote_mailbox,
    )


async def sync_target_and_find_message(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    remote_mailbox: str,
    folder_id: str | None,
    message: JSONDict,
) -> JSONDict | None:
    await sync_mail_account_cache(
        service,
        user_id=user_id,
        account_id=account_id,
        folder_id=folder_id,
        target_remote_mailbox=remote_mailbox,
    )
    target_folder_id = folder_id
    if target_folder_id is None:
        folder_row = await service.database_mail.get_folder_by_remote_mailbox(
            user_id=user_id,
            account_id=account_id,
            remote_mailbox=remote_mailbox,
        )
        if folder_row is None:
            return None
        folder_id_value = folder_row.get("id")
        target_folder_id = folder_id_value.strip() if isinstance(folder_id_value, str) else None
    matched_message_id = await find_message_id_by_message_signature(
        database_mail=service.database_mail,
        user_id=user_id,
        folder_id=target_folder_id,
        message=message,
    )
    if matched_message_id is None:
        return None
    return await service.database_mail.get_message(user_id=user_id, message_id=matched_message_id)


def require_message_uid(message: JSONDict) -> int:
    uid_value = message.get("uid")
    if not isinstance(uid_value, int):
        raise StateError("IMAP message is missing its UID.")
    return uid_value
