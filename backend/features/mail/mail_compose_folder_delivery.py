"""SoAI - Compose special-folder delivery operations [backend/features/mail/mail_compose_folder_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from email.message import EmailMessage
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.types.json import JSONDict
from features.mail.imap_mutations import append_imap_message_sync
from features.mail.internal_protocols import MailRuntimeServiceProtocol
from features.mail.mail_cache_sync import sync_mail_account_cache
from features.mail.mail_folder_targets import resolve_special_folder
from features.mail.mail_message_lookup import find_message_id_by_rfc822_message_id

if TYPE_CHECKING:
    from features.mail.transport_context import PreparedMailTransportContext

__all__ = (
    "append_and_sync_special_folder",
    "save_draft_message",
)

OPERATION = "features.mail.mail_compose_folder_delivery"
LOGGER_NAME = "SoAI.features.mail.mail_compose_folder_delivery"


async def append_and_sync_special_folder(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    prepared: PreparedMailTransportContext,
    special_use: str,
    message: EmailMessage,
    draft: bool,
    rfc822_message_id: str,
) -> str | None:
    if prepared.runtime_state.protocol != "imap":
        return None
    folder_id, remote_mailbox, timeout_sec = await _resolve_special_folder_target(
        self,
        user_id=user_id,
        account_id=account_id,
        prepared=prepared,
        special_use=special_use,
        draft=draft,
    )
    if remote_mailbox is None:
        return None
    await run_bounded_blocking_call(
        self.mail_blocking_pool,
        partial(
            append_imap_message_sync,
            runtime_state=prepared.runtime_state,
            auth_payload=prepared.auth_payload,
            connect_timeout_sec=prepared.connect_timeout_sec,
            connect_host=prepared.inbound_connect_host,
            remote_mailbox=remote_mailbox,
            message=message,
            draft=draft,
        ),
        timeout_sec=timeout_sec,
    )
    await sync_mail_account_cache(
        self,
        user_id=user_id,
        account_id=account_id,
        folder_id=folder_id,
        target_remote_mailbox=remote_mailbox,
    )
    return await find_message_id_by_rfc822_message_id(
        database_mail=self.database_mail,
        user_id=user_id,
        folder_id=folder_id,
        rfc822_message_id=rfc822_message_id,
    )


async def save_draft_message(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    prepared: PreparedMailTransportContext,
    outgoing_message: EmailMessage,
    rfc822_message_id: str,
) -> JSONDict:
    folder_id, remote_mailbox, timeout_sec = await _resolve_special_folder_target(
        self,
        user_id=user_id,
        account_id=account_id,
        prepared=prepared,
        special_use="drafts",
        draft=True,
    )
    if folder_id is None or remote_mailbox is None:
        raise ValidationError("Draft saving requires a configured Drafts folder.")
    await run_bounded_blocking_call(
        self.mail_blocking_pool,
        partial(
            append_imap_message_sync,
            runtime_state=prepared.runtime_state,
            auth_payload=prepared.auth_payload,
            connect_timeout_sec=prepared.connect_timeout_sec,
            connect_host=prepared.inbound_connect_host,
            remote_mailbox=remote_mailbox,
            message=outgoing_message,
            draft=True,
        ),
        timeout_sec=timeout_sec,
    )
    local_message_id: str | None = None
    warnings: list[str] = []
    try:
        await sync_mail_account_cache(
            self,
            user_id=user_id,
            account_id=account_id,
            folder_id=folder_id,
            target_remote_mailbox=remote_mailbox,
        )
        local_message_id = await find_message_id_by_rfc822_message_id(
            database_mail=self.database_mail,
            user_id=user_id,
            folder_id=folder_id,
            rfc822_message_id=rfc822_message_id,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            _mail_compose_folder_delivery_logger(),
            exception,
            message="Failed to sync or confirm Drafts copy after remote draft save.",
            operation=OPERATION,
            level="warning",
            details={"user_id": user_id, "account_id": account_id, "folder_id": folder_id},
        )
        warning_reason = project_public_exception(exception).message
        warnings.append(
            f"Draft was saved remotely, but SoAI could not sync or confirm the Drafts copy: {warning_reason}",
        )
    if local_message_id is None and not warnings:
        warnings.append(
            "Draft was saved remotely, but SoAI could not confirm the Drafts copy in cache.",
        )
    response: JSONDict = {
        "status": "draft_saved",
        "message_id": local_message_id,
        "rfc822_message_id": rfc822_message_id,
    }
    if warnings:
        response["warnings"] = warnings
    return response


async def _resolve_special_folder_target(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    prepared: PreparedMailTransportContext,
    special_use: str,
    draft: bool,
) -> tuple[str | None, str | None, float]:
    folder_id, remote_mailbox = await resolve_special_folder(
        database_mail=self.database_mail,
        user_id=user_id,
        account_id=account_id,
        runtime_state=prepared.runtime_state,
        special_use=special_use,
    )
    if remote_mailbox is None:
        if draft:
            raise ValidationError("Draft saving requires a configured Drafts folder.")
        raise ValidationError("A configured Sent folder is required to store a Sent copy.")
    timeout_sec = prepared.connect_timeout_sec + float(
        self.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC"),
    )
    return folder_id, remote_mailbox, timeout_sec


def _mail_compose_folder_delivery_logger() -> logging.Logger:
    return get_logger(LOGGER_NAME)
