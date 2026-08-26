"""SoAI - Mail attachment query methods [backend/features/mail/message_attachment_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import StateError, ValidationError
from core.files.operations import async_remove_if_exists
from core.types.json import JSONDict
from features.mail.file_uploads import upload_mail_attachment_file
from features.mail.internal_protocols import MailRuntimeServiceProtocol
from features.mail.mail_record_context import require_message_account_id
from features.mail.message_consistency import reload_message_for_locked_account
from features.mail.message_remote_content import (
    extract_attachment_part,
    fetch_remote_message_bytes,
    resolve_attachment_filename,
    write_attachment_temp_file,
)

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext

__all__ = ("download_attachment_method",)


async def download_attachment_method(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    attachment_id: str,
    request_context: RequestContext,
) -> JSONDict:
    part = await self.database_mail.get_attachment_part(
        user_id=user_id,
        attachment_id=attachment_id,
    )
    if part is None:
        raise ValidationError("Attachment not found.")
    message_id_value = part.get("message_id")
    message_id = message_id_value.strip() if isinstance(message_id_value, str) else ""
    if not message_id:
        raise StateError("Attachment is missing its message id.")
    message = await self.database_mail.get_message(user_id=user_id, message_id=message_id)
    if message is None:
        raise ValidationError("Mail message not found.")
    if self.runtime_flags.offline_mode:
        raise ValidationError("Attachment download is unavailable while offline mode is enabled.")
    account_id = require_message_account_id(message)
    filename = ""
    payload_bytes = b""
    mime_type = "application/octet-stream"
    size_bytes = 0
    async with self.account_lock(user_id=user_id, account_id=account_id):
        current_part = await self.database_mail.get_attachment_part(
            user_id=user_id,
            attachment_id=attachment_id,
        )
        if current_part is None:
            raise ValidationError("Attachment not found.")
        current_part_message_id_value = current_part.get("message_id")
        current_part_message_id = (
            current_part_message_id_value.strip()
            if isinstance(current_part_message_id_value, str)
            else ""
        )
        if current_part_message_id != message_id:
            raise StateError("Attachment message changed unexpectedly.")
        current_message = await reload_message_for_locked_account(
            self.database_mail,
            user_id=user_id,
            message_id=message_id,
            account_id=account_id,
        )
        remote_message_bytes = await fetch_remote_message_bytes(
            self,
            user_id=user_id,
            message=current_message,
        )
        part_id_value = current_part.get("part_id")
        part_id = part_id_value.strip() if isinstance(part_id_value, str) else ""
        if not part_id:
            raise StateError("Attachment is missing its part id.")
        selected_part = extract_attachment_part(
            message_bytes=remote_message_bytes,
            part_id=part_id,
        )
        filename = resolve_attachment_filename(selected_part, current_part)
        payload_bytes_value = selected_part.get("payload_bytes")
        if not isinstance(payload_bytes_value, bytes):
            raise StateError("Attachment payload is invalid.")
        payload_bytes = payload_bytes_value
        size_bytes = len(payload_bytes)
        max_bytes = int(self.config.get_int("INTEGRATIONS.MAIL.LIMITS.ATTACHMENT_MAX_BYTES"))
        if size_bytes > max_bytes:
            raise ValidationError("Attachment exceeds the configured maximum size.")
        mime_type_value = selected_part.get("mime_type")
        if not isinstance(mime_type_value, str) or not mime_type_value.strip():
            raise StateError("Attachment mime type is invalid.")
        mime_type = mime_type_value
    temp_file_path = write_attachment_temp_file(
        payload_bytes=payload_bytes,
        filename=filename,
        storage_manager=self.storage_manager,
    )
    try:
        upload_payload = await upload_mail_attachment_file(
            event_bus=self.event_bus,
            request_context=request_context,
            temp_file_path=temp_file_path,
            filename=filename,
        )
    finally:
        temp_file_cleanup = async_remove_if_exists(temp_file_path)
        await uncancel_then_cleanup(temp_file_cleanup)
    file_id_value = upload_payload.get("id")
    file_id = file_id_value.strip() if isinstance(file_id_value, str) else ""
    if not file_id:
        raise StateError("Attachment upload did not return a file id.")
    return {
        "file_id": file_id,
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "file": upload_payload,
    }
