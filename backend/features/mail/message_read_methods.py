"""SoAI - Mail message read methods [backend/features/mail/message_read_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.text.chunked_reads import slice_chunked_text
from core.types.json import JSONDict, JSONValue
from core.validation.integers import is_strict_int
from features.mail.formatting import format_mail_message
from features.mail.internal_protocols import MailRuntimeServiceProtocol
from features.mail.mail_account_context import require_mail_account_protocol
from features.mail.mail_record_context import require_message_account_id
from features.mail.message_consistency import reload_message_for_locked_account
from features.mail.message_remote_content import (
    extract_readable_part,
    fetch_remote_message_bytes,
    parse_remote_message_payload,
)

if TYPE_CHECKING:
    from core.mail.protocols import DatabaseMailProtocol

__all__ = ("read_message_method",)


async def read_message_method(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    message_id: str,
    part_id: str | None,
    max_chars: int,
    offset_chars: int,
) -> JSONDict:
    message = await self.database_mail.get_message(user_id=user_id, message_id=message_id)
    if message is None:
        raise ValidationError("Mail message not found.")
    account_id = require_message_account_id(message)
    async with self.account_lock(user_id=user_id, account_id=account_id):
        current_message = await reload_message_for_locked_account(
            self.database_mail,
            user_id=user_id,
            message_id=message_id,
            account_id=account_id,
        )
        protocol = await _resolve_message_protocol(
            self.database_mail,
            user_id=user_id,
            message=current_message,
        )
        body_text, parts, remote_message_bytes, refreshed_message = (
            await _resolve_message_read_state(
                self,
                user_id=user_id,
                message=current_message,
                part_id=part_id,
            )
        )
        selected_part: JSONDict | None = None
        content = body_text
        if part_id is not None:
            if remote_message_bytes is None:
                raise ValidationError("Requested mail part requires remote access.")
            selected_part = extract_readable_part(
                message_bytes=remote_message_bytes,
                part_id=part_id,
            )
            content = str(selected_part["text"])
        effective_message = refreshed_message if refreshed_message is not None else current_message
        body_value = effective_message.get("body")
        if body_value is None:
            total_chars = len(content)
        elif isinstance(body_value, dict):
            total_chars_value = body_value.get("total_chars")
            if total_chars_value is None:
                total_chars = len(content)
            else:
                if not is_strict_int(total_chars_value):
                    raise StateError("Mail message total_chars is invalid.")
                if total_chars_value < 0:
                    raise StateError("Mail message total_chars is invalid.")
                total_chars = total_chars_value
        else:
            raise StateError("Mail message body is invalid.")
        chunk = slice_chunked_text(
            content=content,
            max_chars=max(1, max_chars),
            offset_chars=max(offset_chars, 0),
            content_complete=True,
        )
        response = {
            "message": format_mail_message(effective_message, protocol=protocol),
            "part_id": part_id,
            "parts": parts,
            "content": chunk.content,
            "truncated": chunk.truncated,
            "offset_chars": chunk.offset_chars,
            "next_offset_chars": chunk.next_offset_chars,
            "total_chars": total_chars,
            "warnings": list(chunk.warnings),
            "invite": effective_message.get("invite"),
        }
        if selected_part is not None:
            response["selected_part"] = {
                "part_id": selected_part["part_id"],
                "mime_type": selected_part["mime_type"],
                "filename": selected_part["filename"],
                "is_inline": selected_part["is_inline"],
            }
        return response


async def _resolve_message_protocol(
    database_mail: DatabaseMailProtocol,
    *,
    user_id: int,
    message: JSONDict,
) -> str:
    account_id = require_message_account_id(message)
    account = await database_mail.get_account(user_id=user_id, account_id=account_id)
    if account is None:
        raise StateError("Mail account not found.")
    return require_mail_account_protocol(account)


async def _resolve_message_read_state(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    message: JSONDict,
    part_id: str | None,
) -> tuple[str, list[JSONDict], bytes | None, JSONDict | None]:
    parts_value = message.get("parts")
    parts = _normalize_message_parts(parts_value)
    body_value = message.get("body")
    if body_value is None:
        body_text = ""
    elif isinstance(body_value, dict):
        body_text_value = body_value.get("body_text")
        if body_text_value is None:
            body_text = ""
        elif isinstance(body_text_value, str):
            body_text = body_text_value
        else:
            raise StateError("Mail message body_text is invalid.")
    else:
        raise StateError("Mail message body is invalid.")
    remote_message_bytes: bytes | None = None
    refreshed_message: JSONDict | None = None
    needs_remote_fetch = part_id is not None or not body_text
    if not needs_remote_fetch:
        return body_text, parts, None, None
    if self.runtime_flags.offline_mode:
        raise ValidationError("Mail message content is not cached and offline mode is enabled.")
    remote_message_bytes = await fetch_remote_message_bytes(
        self,
        user_id=user_id,
        message=message,
    )
    parsed_payload = parse_remote_message_payload(
        message=message,
        message_bytes=remote_message_bytes,
    )
    message_id_value = message.get("id")
    message_id = message_id_value.strip() if isinstance(message_id_value, str) else ""
    if not message_id:
        raise StateError("Mail message is missing its id.")
    parsed_parts_value = parsed_payload.get("parts")
    parsed_parts = _normalize_message_parts(parsed_parts_value)
    body_text_value = parsed_payload.get("body_text")
    if not isinstance(body_text_value, str):
        raise StateError("Mail remote payload body_text is invalid.")
    body_text = body_text_value
    body_html_value = parsed_payload.get("body_html")
    if body_html_value is None:
        body_html = None
    elif isinstance(body_html_value, str) and body_html_value.strip():
        body_html = body_html_value
    else:
        raise StateError("Mail remote payload body_html is invalid.")
    refreshed_body = await self.database_mail.replace_message_body(
        user_id=user_id,
        message_id=message_id,
        body_text=body_text,
        body_html=body_html,
        total_chars=len(body_text),
        parts=parsed_parts,
    )
    if refreshed_body is None:
        raise StateError("Mail message disappeared after body refresh.")
    refreshed_message = await self.database_mail.get_message(
        user_id=user_id,
        message_id=message_id,
    )
    if refreshed_message is None:
        raise StateError("Mail message disappeared after body refresh.")
    refreshed_parts_value = refreshed_message.get("parts")
    refreshed_parts = _normalize_message_parts(refreshed_parts_value)
    refreshed_body_text_value = refreshed_body.get("body_text")
    if not isinstance(refreshed_body_text_value, str):
        raise StateError("Mail refreshed message body_text is invalid.")
    return refreshed_body_text_value, refreshed_parts, remote_message_bytes, refreshed_message


def _normalize_message_parts(parts_value: JSONValue) -> list[JSONDict]:
    if parts_value is None:
        return []
    if not isinstance(parts_value, list):
        raise StateError("Mail message parts is invalid.")
    normalized_parts: list[JSONDict] = []
    for item in parts_value:
        if not isinstance(item, dict):
            raise StateError("Mail message part entry is invalid.")
        normalized_part: JSONDict = {}
        for key, value in item.items():
            if not isinstance(key, str):
                raise StateError("Mail message part key is invalid.")
            normalized_part[key] = value
        normalized_parts.append(normalized_part)
    return normalized_parts
