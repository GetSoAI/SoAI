"""SoAI - Mail message state mutations [backend/features/mail/mail_message_state_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.errors.exceptions import StateError, ValidationError
from core.types.json import JSONDict
from features.mail.formatting import format_mail_message
from features.mail.imap_mutations import set_imap_message_flags_sync
from features.mail.internal_protocols import MailRuntimeServiceProtocol
from features.mail.mail_cache_sync import sync_mail_account_cache
from features.mail.mail_message_context import (
    LoadedMailMessageContext,
    require_message_uid,
)
from features.mail.pop3_mutations import delete_pop3_message_sync
from features.mail.transport_context import PreparedMailTransportContext
from features.mail.transport_preparation import prepare_service_mail_transport_context

__all__ = (
    "mutate_pop3_message",
    "update_imap_flags",
)


async def mutate_pop3_message(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    context: LoadedMailMessageContext,
    action: str,
) -> JSONDict:
    if action == "mark_read":
        updated = await service.database_mail.update_message(
            user_id=user_id,
            message_id=str(context.message["id"]),
            updates={"unread": False},
        )
        if updated is None:
            raise ValidationError("Mail message not found.")
        return format_mail_message(updated, protocol="pop3")
    if action == "mark_unread":
        updated = await service.database_mail.update_message(
            user_id=user_id,
            message_id=str(context.message["id"]),
            updates={"unread": True},
        )
        if updated is None:
            raise ValidationError("Mail message not found.")
        return format_mail_message(updated, protocol="pop3")
    if action != "delete":
        raise ValidationError("POP3 supports only mark_read, mark_unread, and delete.")
    uidl_value = context.message.get("uidl")
    uidl = uidl_value.strip() if isinstance(uidl_value, str) else ""
    if not uidl:
        raise StateError("POP3 message is missing its UIDL.")
    prepared = await prepare_service_mail_transport_context(
        service,
        user_id=user_id,
        account_id=context.account_id,
    )
    await run_bounded_blocking_call(
        service.mail_blocking_pool,
        partial(
            delete_pop3_message_sync,
            runtime_state=prepared.runtime_state,
            auth_payload=prepared.auth_payload,
            connect_timeout_sec=prepared.connect_timeout_sec,
            connect_host=prepared.inbound_connect_host,
            uidl=uidl,
        ),
        timeout_sec=prepared.connect_timeout_sec
        + float(service.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
    )
    deleted_snapshot = format_mail_message(context.message, protocol="pop3")
    deleted_snapshot["deleted"] = True
    await service.database_mail.delete_message(
        user_id=user_id,
        message_id=str(context.message["id"]),
    )
    await sync_mail_account_cache(
        service,
        user_id=user_id,
        account_id=context.account_id,
        folder_id=context.folder_id,
    )
    return deleted_snapshot


async def update_imap_flags(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    context: LoadedMailMessageContext,
    prepared: PreparedMailTransportContext,
    action: str,
    flag: str,
    local_updates: JSONDict,
) -> JSONDict:
    await run_bounded_blocking_call(
        service.mail_blocking_pool,
        partial(
            set_imap_message_flags_sync,
            runtime_state=prepared.runtime_state,
            auth_payload=prepared.auth_payload,
            connect_timeout_sec=prepared.connect_timeout_sec,
            connect_host=prepared.inbound_connect_host,
            remote_mailbox=context.remote_mailbox,
            uid=require_message_uid(context.message),
            mode="+FLAGS.SILENT" if action in {"mark_read", "flag"} else "-FLAGS.SILENT",
            flags=(flag,),
        ),
        timeout_sec=prepared.connect_timeout_sec
        + float(service.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
    )
    updated = await service.database_mail.update_message(
        user_id=user_id,
        message_id=str(context.message["id"]),
        updates=local_updates,
    )
    if updated is None:
        raise ValidationError("Mail message not found.")
    return updated
