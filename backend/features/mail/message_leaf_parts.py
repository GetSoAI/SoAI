"""SoAI - Mail MIME leaf-part helpers [backend/features/mail/message_leaf_parts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from email.message import Message
from typing import TYPE_CHECKING, TypeGuard

from core.users.account_identifiers import MAIL_ATTACHMENT_ID_PREFIX

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_attachment_id",
    "decode_message_part_text",
    "extract_message_part_payload",
    "is_attachment_part",
    "is_inline_part",
    "iter_leaf_parts",
    "read_message_part_bytes",
)


def _is_message_part(value: Message | str) -> TypeGuard[Message]:
    return isinstance(value, Message)


def iter_leaf_parts(message: Message, *, prefix: str) -> list[tuple[str, Message]]:
    if not message.is_multipart():
        return [(prefix, message)]
    payload = message.get_payload(decode=False)
    if not isinstance(payload, list):
        return [(prefix, message)]
    items: list[tuple[str, Message]] = []
    payload_index = 0
    while True:
        try:
            part = message.get_payload(payload_index)
        except IndexError:
            break
        if not _is_message_part(part):
            payload_index += 1
            continue
        child_prefix = f"{prefix}.{payload_index + 1}"
        items.extend(iter_leaf_parts(part, prefix=child_prefix))
        payload_index += 1
    return items


def extract_message_part_payload(
    message: Message,
    *,
    part_id: str,
) -> JSONDict | None:
    for leaf_part_id, part in iter_leaf_parts(message, prefix="1"):
        if leaf_part_id != part_id:
            continue
        mime_type = part.get_content_type().strip().lower()
        filename_value = part.get_filename()
        filename = filename_value.strip() if isinstance(filename_value, str) else None
        payload_bytes = read_message_part_bytes(part)
        is_attachment = is_attachment_part(part, filename=filename)
        return {
            "part_id": leaf_part_id,
            "mime_type": mime_type,
            "filename": filename,
            "is_attachment": is_attachment,
            "is_inline": is_inline_part(part, is_attachment=is_attachment),
            "payload_bytes": payload_bytes,
            "text": decode_message_part_text(part, payload_bytes),
        }
    return None


def read_message_part_bytes(part: Message) -> bytes:
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        charset = _resolve_charset(part)
        return payload.encode(charset, errors="replace")
    return b""


def decode_message_part_text(part: Message, payload_bytes: bytes) -> str:
    if not payload_bytes:
        return ""
    charset = _resolve_charset(part)
    return payload_bytes.decode(charset, errors="replace").strip()


def is_attachment_part(part: Message, *, filename: str | None) -> bool:
    disposition = part.get_content_disposition()
    if disposition == "attachment":
        return True
    if filename:
        return True
    mime_type = part.get_content_type().strip().lower()
    return not mime_type.startswith("text/")


def is_inline_part(part: Message, *, is_attachment: bool) -> bool:
    if is_attachment:
        return False
    disposition = part.get_content_disposition()
    return disposition in {"inline", None}


def build_attachment_id(*, attachment_identity_key: str, part_id: str) -> str:
    digest = hashlib.sha256(f"{attachment_identity_key}:{part_id}".encode()).hexdigest()
    return f"{MAIL_ATTACHMENT_ID_PREFIX}{digest[:24]}"


def _resolve_charset(part: Message) -> str:
    charset = part.get_content_charset()
    if isinstance(charset, str) and charset.strip():
        return charset.strip()
    return "utf-8"
