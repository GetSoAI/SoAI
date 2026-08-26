"""SoAI - Mail message mutation dispatch [backend/features/mail/mail_message_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from features.mail.formatting import format_mail_message
from features.mail.internal_protocols import MailRuntimeServiceProtocol
from features.mail.mail_message_context import (
    load_message_context,
    resolve_explicit_destination,
)
from features.mail.mail_message_state_mutations import (
    mutate_pop3_message,
    update_imap_flags,
)
from features.mail.mail_message_transfer_mutations import (
    copy_imap_message,
    delete_imap_message,
    move_imap_message,
    resolve_archive_destination,
)
from features.mail.transport_preparation import prepare_service_mail_transport_context

__all__ = ("mutate_message_method",)


async def mutate_message_method(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    message_id: str,
    action: str,
    destination_folder_id: str | None,
) -> JSONDict:
    context = await load_message_context(service, user_id=user_id, message_id=message_id)
    async with service.account_lock(user_id=user_id, account_id=context.account_id):
        context = await load_message_context(service, user_id=user_id, message_id=message_id)
        if context.protocol == "pop3":
            return await mutate_pop3_message(
                service,
                user_id=user_id,
                context=context,
                action=action,
            )
        prepared = await prepare_service_mail_transport_context(
            service,
            user_id=user_id,
            account_id=context.account_id,
        )
        if action in {"mark_read", "mark_unread"}:
            updated = await update_imap_flags(
                service,
                user_id=user_id,
                context=context,
                prepared=prepared,
                action=action,
                flag="\\Seen",
                local_updates={"unread": action != "mark_read"},
            )
            return format_mail_message(updated, protocol="imap")
        if action in {"flag", "unflag"}:
            updated = await update_imap_flags(
                service,
                user_id=user_id,
                context=context,
                prepared=prepared,
                action=action,
                flag="\\Flagged",
                local_updates={"flagged": action == "flag"},
            )
            return format_mail_message(updated, protocol="imap")
        if action == "copy":
            return await copy_imap_message(
                service,
                user_id=user_id,
                context=context,
                prepared=prepared,
                destination_folder_id=destination_folder_id,
            )
        if action == "move":
            destination = await resolve_explicit_destination(
                service,
                user_id=user_id,
                account_id=context.account_id,
                destination_folder_id=destination_folder_id,
            )
            return await move_imap_message(
                service,
                user_id=user_id,
                context=context,
                prepared=prepared,
                destination_remote_mailbox=destination.remote_mailbox,
                destination_folder_id=destination.folder_id,
                deleted_original_folder_id=None,
                deleted=False,
            )
        if action == "archive":
            destination = await resolve_archive_destination(
                service,
                user_id=user_id,
                context=context,
                prepared=prepared,
                special_use="archive",
            )
            return await move_imap_message(
                service,
                user_id=user_id,
                context=context,
                prepared=prepared,
                destination_remote_mailbox=destination.remote_mailbox,
                destination_folder_id=destination.folder_id,
                deleted_original_folder_id=None,
                deleted=False,
            )
        if action == "unarchive":
            destination = await resolve_archive_destination(
                service,
                user_id=user_id,
                context=context,
                prepared=prepared,
                special_use="inbox",
            )
            return await move_imap_message(
                service,
                user_id=user_id,
                context=context,
                prepared=prepared,
                destination_remote_mailbox=destination.remote_mailbox,
                destination_folder_id=destination.folder_id,
                deleted_original_folder_id=None,
                deleted=False,
            )
        if action == "delete":
            return await delete_imap_message(
                service,
                user_id=user_id,
                context=context,
                prepared=prepared,
            )
        if action == "restore":
            destination = await resolve_archive_destination(
                service,
                user_id=user_id,
                context=context,
                prepared=prepared,
                special_use="restore",
            )
            return await move_imap_message(
                service,
                user_id=user_id,
                context=context,
                prepared=prepared,
                destination_remote_mailbox=destination.remote_mailbox,
                destination_folder_id=destination.folder_id,
                deleted_original_folder_id=None,
                deleted=False,
            )
        raise ValidationError("mail_message_update.action is invalid.")
