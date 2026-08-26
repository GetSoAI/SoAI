"""SoAI - Mail folder mutations [backend/features/mail/mail_folder_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.errors.exceptions import StateError, ValidationError
from core.types.json import JSONDict
from core.validation.strings import require_trimmed_text
from features.mail.formatting import format_mail_folder
from features.mail.imap_mailbox_mutations import (
    create_imap_mailbox_sync,
    delete_imap_mailbox_sync,
    rename_imap_mailbox_sync,
    set_imap_subscription_sync,
)
from features.mail.internal_protocols import MailRuntimeServiceProtocol
from features.mail.mail_cache_sync import sync_mail_account_cache
from features.mail.mail_record_context import (
    require_folder_account_id,
    require_folder_remote_mailbox,
)
from features.mail.transport_preparation import prepare_service_mail_transport_context

__all__ = ("mutate_folder_method",)


async def mutate_folder_method(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    action: str,
    folder_id: str | None,
    folder_name: str | None,
) -> JSONDict:
    async with service.account_lock(user_id=user_id, account_id=account_id):
        account = await service.database_mail.get_account(user_id=user_id, account_id=account_id)
        if account is None:
            raise ValidationError("Mail account not found.")
        protocol_value = account.get("protocol")
        protocol = protocol_value.strip().lower() if isinstance(protocol_value, str) else ""
        if protocol != "imap":
            raise ValidationError("Mail folder mutation requires an IMAP account.")
        prepared = await prepare_service_mail_transport_context(
            service,
            user_id=user_id,
            account_id=account_id,
        )
        if action == "create":
            remote_mailbox = require_trimmed_text(
                folder_name,
                "folder_name is required for create.",
            )
            await run_bounded_blocking_call(
                service.mail_blocking_pool,
                partial(
                    create_imap_mailbox_sync,
                    runtime_state=prepared.runtime_state,
                    auth_payload=prepared.auth_payload,
                    connect_timeout_sec=prepared.connect_timeout_sec,
                    connect_host=prepared.inbound_connect_host,
                    folder_name=remote_mailbox,
                ),
                timeout_sec=prepared.connect_timeout_sec
                + float(service.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
            )
            await sync_mail_account_cache(
                service,
                user_id=user_id,
                account_id=account_id,
                folder_id=None,
                target_remote_mailbox=remote_mailbox,
            )
            created_folder = await service.database_mail.get_folder_by_remote_mailbox(
                user_id=user_id,
                account_id=account_id,
                remote_mailbox=remote_mailbox,
            )
            if created_folder is None:
                raise StateError("Created mail folder could not be loaded.")
            return format_mail_folder(created_folder, protocol="imap")
        source_folder = await _require_folder(
            service,
            user_id=user_id,
            folder_id=folder_id,
            account_id=account_id,
        )
        remote_mailbox = require_folder_remote_mailbox(source_folder)
        if action == "rename":
            new_remote_mailbox = require_trimmed_text(
                folder_name,
                "folder_name is required for rename.",
            )
            if new_remote_mailbox == remote_mailbox:
                return format_mail_folder(source_folder, protocol="imap")
            await run_bounded_blocking_call(
                service.mail_blocking_pool,
                partial(
                    rename_imap_mailbox_sync,
                    runtime_state=prepared.runtime_state,
                    auth_payload=prepared.auth_payload,
                    connect_timeout_sec=prepared.connect_timeout_sec,
                    connect_host=prepared.inbound_connect_host,
                    remote_mailbox=remote_mailbox,
                    new_remote_mailbox=new_remote_mailbox,
                ),
                timeout_sec=prepared.connect_timeout_sec
                + float(service.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
            )
            await service.database_mail.delete_folder(
                user_id=user_id,
                folder_id=str(source_folder["id"]),
            )
            await sync_mail_account_cache(
                service,
                user_id=user_id,
                account_id=account_id,
                folder_id=None,
                target_remote_mailbox=new_remote_mailbox,
            )
            renamed_folder = await service.database_mail.get_folder_by_remote_mailbox(
                user_id=user_id,
                account_id=account_id,
                remote_mailbox=new_remote_mailbox,
            )
            if renamed_folder is None:
                raise StateError("Renamed mail folder could not be loaded.")
            return format_mail_folder(renamed_folder, protocol="imap")
        if action == "delete":
            deleted_snapshot = format_mail_folder(source_folder, protocol="imap")
            deleted_snapshot["deleted"] = True
            await run_bounded_blocking_call(
                service.mail_blocking_pool,
                partial(
                    delete_imap_mailbox_sync,
                    runtime_state=prepared.runtime_state,
                    auth_payload=prepared.auth_payload,
                    connect_timeout_sec=prepared.connect_timeout_sec,
                    connect_host=prepared.inbound_connect_host,
                    remote_mailbox=remote_mailbox,
                ),
                timeout_sec=prepared.connect_timeout_sec
                + float(service.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
            )
            await service.database_mail.delete_folder(
                user_id=user_id,
                folder_id=str(source_folder["id"]),
            )
            return deleted_snapshot
        if action in {"subscribe", "unsubscribe"}:
            subscribed = action == "subscribe"
            await run_bounded_blocking_call(
                service.mail_blocking_pool,
                partial(
                    set_imap_subscription_sync,
                    runtime_state=prepared.runtime_state,
                    auth_payload=prepared.auth_payload,
                    connect_timeout_sec=prepared.connect_timeout_sec,
                    connect_host=prepared.inbound_connect_host,
                    remote_mailbox=remote_mailbox,
                    subscribed=subscribed,
                ),
                timeout_sec=prepared.connect_timeout_sec
                + float(service.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
            )
            folder_payload = dict(source_folder)
            folder_payload["subscribed"] = subscribed
            updated_folder = await service.database_mail.upsert_folder(
                user_id=user_id,
                account_id=account_id,
                payload=folder_payload,
            )
            return format_mail_folder(updated_folder, protocol="imap")
        raise ValidationError("mail_folder_update.action is invalid.")


async def _require_folder(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    folder_id: str | None,
    account_id: str,
) -> JSONDict:
    if folder_id is None:
        raise ValidationError("folder_id is required for this action.")
    folder = await service.database_mail.get_folder(user_id=user_id, folder_id=folder_id)
    if folder is None:
        raise ValidationError("Mail folder not found.")
    folder_account_id = require_folder_account_id(folder)
    if folder_account_id != account_id:
        raise ValidationError("Mail folder belongs to another account.")
    return folder
