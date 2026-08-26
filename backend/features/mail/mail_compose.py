"""SoAI - Mail compose and delivery methods [backend/features/mail/mail_compose.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from email.message import EmailMessage
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.types.json import JSONDict
from core.validation.strings import coerce_trimmed_str_or_empty
from features.mail.auth_payload_fields import require_mail_auth_payload_username
from features.mail.file_uploads import load_attachment_file_records
from features.mail.internal_protocols import MailRuntimeServiceProtocol
from features.mail.mail_compose_folder_delivery import (
    append_and_sync_special_folder,
    save_draft_message,
)
from features.mail.outgoing_message import (
    build_outgoing_message,
    resolve_attachment_file_ids,
)
from features.mail.smtp_transport import send_smtp_message_sync
from features.mail.transport_preparation import prepare_service_mail_transport_context

if TYPE_CHECKING:
    from features.mail.transport_context import PreparedMailTransportContext

__all__ = ("compose_message_method",)

OPERATION = "features.mail.mail_compose"
LOGGER_NAME = "SoAI.features.mail.mail_compose"


async def compose_message_method(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    payload: JSONDict,
) -> JSONDict:
    account_id_value = payload.get("account_id")
    account_id = coerce_trimmed_str_or_empty(account_id_value)
    if not account_id:
        raise ValidationError("account_id is required.")
    async with self.account_lock(user_id=user_id, account_id=account_id):
        prepared = await prepare_service_mail_transport_context(
            self,
            user_id=user_id,
            account_id=account_id,
        )
        username = require_mail_auth_payload_username(prepared.auth_payload)
        base_message, base_body_text = await _load_base_message(
            self,
            user_id=user_id,
            account_id=account_id,
            payload=payload,
        )
        file_ids = resolve_attachment_file_ids(payload)
        attachment_records = await load_attachment_file_records(
            database_files=self.database_files,
            user_id=user_id,
            file_ids=file_ids,
        )
        resolved_payload = dict(payload)
        resolved_payload["protocol"] = prepared.runtime_state.protocol
        outgoing_message, rfc822_message_id = build_outgoing_message(
            payload=resolved_payload,
            username=username,
            base_message=base_message,
            base_body_text=base_body_text,
            attachment_records=attachment_records,
        )
        delivery_value = payload.get("delivery")
        delivery = coerce_trimmed_str_or_empty(delivery_value)
        timeout_sec = prepared.connect_timeout_sec + float(
            self.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC"),
        )
        if delivery == "send":
            return await _send_outgoing_message(
                self,
                user_id=user_id,
                account_id=account_id,
                prepared=prepared,
                timeout_sec=timeout_sec,
                outgoing_message=outgoing_message,
                rfc822_message_id=rfc822_message_id,
            )
        if delivery != "save_draft":
            raise ValidationError("delivery is invalid.")
        if prepared.runtime_state.protocol != "imap":
            raise ValidationError("Draft saving is available only for IMAP accounts.")
        return await save_draft_message(
            self,
            user_id=user_id,
            account_id=account_id,
            prepared=prepared,
            outgoing_message=outgoing_message,
            rfc822_message_id=rfc822_message_id,
        )


async def _load_base_message(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    payload: JSONDict,
) -> tuple[JSONDict | None, str | None]:
    base_message_id_value = payload.get("base_message_id")
    base_message_id = coerce_trimmed_str_or_empty(base_message_id_value)
    if not base_message_id:
        return None, None
    base_message = await self.database_mail.get_message(user_id=user_id, message_id=base_message_id)
    if base_message is None:
        raise ValidationError("base_message_id does not exist.")
    base_account_id_value = base_message.get("mail_account_id")
    base_account_id = coerce_trimmed_str_or_empty(base_account_id_value)
    if base_account_id != account_id:
        raise ValidationError("base_message_id belongs to another mail account.")
    body_value = base_message.get("body")
    if body_value is None:
        return base_message, None
    if not isinstance(body_value, dict):
        raise StateError("Mail base message body is invalid.")
    body_text_value = body_value.get("body_text")
    if body_text_value is None:
        return base_message, None
    if not isinstance(body_text_value, str):
        raise StateError("Mail base message body_text is invalid.")
    return base_message, body_text_value


async def _send_outgoing_message(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    prepared: PreparedMailTransportContext,
    timeout_sec: float,
    outgoing_message: EmailMessage,
    rfc822_message_id: str,
) -> JSONDict:
    await run_bounded_blocking_call(
        self.mail_blocking_pool,
        partial(
            send_smtp_message_sync,
            runtime_state=prepared.runtime_state,
            auth_payload=prepared.auth_payload,
            message=outgoing_message,
            connect_timeout_sec=prepared.connect_timeout_sec,
            connect_host=prepared.smtp_connect_host,
        ),
        timeout_sec=timeout_sec,
    )
    local_message_id: str | None = None
    warnings: list[str] = []
    try:
        local_message_id = await append_and_sync_special_folder(
            self,
            user_id=user_id,
            account_id=account_id,
            prepared=prepared,
            special_use="sent",
            message=outgoing_message,
            draft=False,
            rfc822_message_id=rfc822_message_id,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            _mail_compose_logger(),
            exception,
            message="Failed to append or sync Sent folder copy after message send.",
            operation=OPERATION,
            level="warning",
            details={"user_id": user_id, "account_id": account_id},
        )
        warning_reason = project_public_exception(exception).message
        warnings.append(
            f"Message was sent, but SoAI could not save or sync the Sent copy: {warning_reason}",
        )
    if local_message_id is None and not warnings and prepared.runtime_state.protocol == "imap":
        warnings.append("Message was sent, but SoAI could not confirm the Sent copy in cache.")
    response: JSONDict = {
        "status": "sent",
        "message_id": local_message_id,
        "rfc822_message_id": rfc822_message_id,
    }
    if warnings:
        response["warnings"] = warnings
    return response


def _mail_compose_logger() -> logging.Logger:
    return get_logger(LOGGER_NAME)
