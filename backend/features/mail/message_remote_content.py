"""SoAI - Mail remote message content helpers [backend/features/mail/message_remote_content.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from email import policy
from email.parser import BytesParser
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError, StateError, ValidationError
from core.files.temp_files import create_secure_temp_file_descriptor
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.types.json import JSONDict
from features.mail.imap_reads import fetch_imap_message_bytes_for_account_sync
from features.mail.internal_protocols import MailRemoteContentServiceProtocol
from features.mail.mail_record_context import require_message_account_id
from features.mail.message_leaf_parts import extract_message_part_payload
from features.mail.message_parsing import parse_message_bytes
from features.mail.pop3_reads import fetch_pop3_message_bytes_sync
from features.mail.transport_context import prepare_mail_transport_context

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = (
    "extract_attachment_part",
    "extract_readable_part",
    "fetch_remote_message_bytes",
    "parse_remote_message_payload",
    "resolve_attachment_filename",
    "write_attachment_temp_file",
)

LOGGER_NAME = "SoAI.features.mail.message_remote_content"
OPERATION_CLEANUP_ATTACHMENT_TEMP_FILE = "features.mail.attachment.temp_write.cleanup"


async def fetch_remote_message_bytes(
    service: MailRemoteContentServiceProtocol,
    *,
    user_id: int,
    message: JSONDict,
) -> bytes:
    message_id_value = message.get("id")
    message_id = message_id_value.strip() if isinstance(message_id_value, str) else ""
    if not message_id:
        raise StateError("Mail message is missing its id.")
    account_id = require_message_account_id(message)
    async with service.account_lock(user_id=user_id, account_id=account_id):
        current_message = await service.database_mail.get_message(
            user_id=user_id,
            message_id=message_id,
        )
        if current_message is None:
            raise ValidationError("Mail message not found.")
        current_account_id = require_message_account_id(current_message)
        if current_account_id != account_id:
            raise StateError("Mail message account changed unexpectedly.")
        prepared = await prepare_mail_transport_context(
            config=service.config,
            runtime_flags=service.runtime_flags,
            database_mail=service.database_mail,
            external_accounts=service.external_accounts,
            user_id=user_id,
            account_id=current_account_id,
        )
        timeout_sec = prepared.connect_timeout_sec + float(
            service.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC"),
        )
        if prepared.runtime_state.protocol == "imap":
            remote_mailbox_value = current_message.get("remote_mailbox")
            remote_mailbox = (
                remote_mailbox_value.strip() if isinstance(remote_mailbox_value, str) else ""
            )
            uid_value = current_message.get("uid")
            uid = uid_value if isinstance(uid_value, int) else None
            if not remote_mailbox or uid is None:
                raise StateError("IMAP message is missing remote fetch identity.")
            return await run_bounded_blocking_call(
                service.mail_blocking_pool,
                partial(
                    fetch_imap_message_bytes_for_account_sync,
                    runtime_state=prepared.runtime_state,
                    auth_payload=prepared.auth_payload,
                    connect_timeout_sec=prepared.connect_timeout_sec,
                    connect_host=prepared.inbound_connect_host,
                    remote_mailbox=remote_mailbox,
                    uid=uid,
                ),
                timeout_sec=timeout_sec,
            )
        uidl_value = current_message.get("uidl")
        uidl = uidl_value.strip() if isinstance(uidl_value, str) else ""
        if not uidl:
            raise StateError("POP3 message is missing remote fetch identity.")
        return await run_bounded_blocking_call(
            service.mail_blocking_pool,
            partial(
                fetch_pop3_message_bytes_sync,
                runtime_state=prepared.runtime_state,
                auth_payload=prepared.auth_payload,
                connect_timeout_sec=prepared.connect_timeout_sec,
                connect_host=prepared.inbound_connect_host,
                uidl=uidl,
            ),
            timeout_sec=timeout_sec,
        )


def parse_remote_message_payload(*, message: JSONDict, message_bytes: bytes) -> JSONDict:
    remote_mailbox_value = message.get("remote_mailbox")
    uidvalidity_value = message.get("uidvalidity")
    uid_value = message.get("uid")
    uidl_value = message.get("uidl")
    received_at_ms_value = message.get("received_at_ms")
    return parse_message_bytes(
        message_bytes=message_bytes,
        remote_mailbox=remote_mailbox_value if isinstance(remote_mailbox_value, str) else None,
        uidvalidity=uidvalidity_value if isinstance(uidvalidity_value, int) else None,
        uid=uid_value if isinstance(uid_value, int) else None,
        uidl=uidl_value if isinstance(uidl_value, str) else None,
        received_at_ms=received_at_ms_value if isinstance(received_at_ms_value, int) else 0,
        unread=message.get("unread") is True,
        flagged=message.get("flagged") is True,
        attachment_identity_key=_resolve_attachment_identity_key(message),
        snippet_max_chars=int(max(len(str(message.get("snippet") or "")), 500)),
    )


def extract_readable_part(*, message_bytes: bytes, part_id: str) -> JSONDict:
    message = BytesParser(policy=policy.default).parsebytes(message_bytes)
    payload = extract_message_part_payload(message, part_id=part_id)
    if payload is None:
        raise ValidationError("Mail part not found.")
    text_value = payload.get("text")
    text = text_value if isinstance(text_value, str) and text_value else ""
    if not text:
        raise ValidationError("Requested mail part is not readable as text.")
    return payload


def extract_attachment_part(*, message_bytes: bytes, part_id: str) -> JSONDict:
    message = BytesParser(policy=policy.default).parsebytes(message_bytes)
    payload = extract_message_part_payload(message, part_id=part_id)
    if payload is None:
        raise ValidationError("Attachment part not found.")
    is_attachment_value = payload.get("is_attachment")
    if is_attachment_value is not True:
        raise ValidationError("Requested mail part is not an attachment.")
    return payload


def resolve_attachment_filename(selected_part: JSONDict, part: JSONDict) -> str:
    filename_value = selected_part.get("filename")
    if isinstance(filename_value, str) and filename_value.strip():
        return filename_value.strip()
    part_filename_value = part.get("filename")
    if isinstance(part_filename_value, str) and part_filename_value.strip():
        return part_filename_value.strip()
    return "attachment.bin"


def _cleanup_attachment_temp_file(*, file_descriptor: int, temp_path: str) -> None:
    logger = get_logger(LOGGER_NAME)
    if file_descriptor != -1:
        try:
            os.close(file_descriptor)
        except OSError as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to close mail attachment temp file descriptor after failure.",
                operation=OPERATION_CLEANUP_ATTACHMENT_TEMP_FILE,
                level="debug",
            )
    if temp_path:
        try:
            os.remove(temp_path)
        except OSError as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to remove mail attachment temp file after failure.",
                operation=OPERATION_CLEANUP_ATTACHMENT_TEMP_FILE,
                details={"temp_path": temp_path},
                level="debug",
            )


def write_attachment_temp_file(
    *,
    payload_bytes: bytes,
    filename: str,
    storage_manager: StorageManagerProtocol,
) -> str:
    _root, extension = os.path.splitext(filename)
    file_descriptor = -1
    temp_path = ""
    try:
        file_descriptor, temp_path = create_secure_temp_file_descriptor(
            directory=None,
            prefix="soai-",
            suffix=extension or ".bin",
        )
        required_bytes = len(payload_bytes)
        with (
            storage_manager.reserve_disk_space(
                path=temp_path,
                required_bytes=required_bytes,
                operation="features.mail.attachment.temp_write",
                details={"filename": filename, "required_bytes": required_bytes},
            ) as reservation,
            claim_reserved_write(reservation, size_bytes=required_bytes),
        ):
            with os.fdopen(file_descriptor, "wb") as handle:
                file_descriptor = -1
                handle.write(payload_bytes)
        return temp_path
    except (OSError, SoAIError):
        _cleanup_attachment_temp_file(
            file_descriptor=file_descriptor,
            temp_path=temp_path,
        )
        raise


def _resolve_attachment_identity_key(message: JSONDict) -> str:
    account_id_value = message.get("mail_account_id")
    account_id = account_id_value.strip() if isinstance(account_id_value, str) else ""
    uidl_value = message.get("uidl")
    if isinstance(uidl_value, str) and uidl_value.strip():
        return f"pop3:{account_id}:{uidl_value.strip()}"
    remote_mailbox_value = message.get("remote_mailbox")
    remote_mailbox = remote_mailbox_value.strip() if isinstance(remote_mailbox_value, str) else ""
    uidvalidity_value = message.get("uidvalidity")
    uid_value = message.get("uid")
    uidvalidity = uidvalidity_value if isinstance(uidvalidity_value, int) else 0
    uid = uid_value if isinstance(uid_value, int) else 0
    return f"imap:{account_id}:{remote_mailbox}:{uidvalidity}:{uid}"
