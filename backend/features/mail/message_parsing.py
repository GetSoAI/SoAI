"""SoAI - Mail MIME normalization helpers [backend/features/mail/message_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from email import policy
from email.parser import BytesParser

from core.types.json import JSONDict
from core.web.html_metadata import extract_html_text_excerpt
from features.mail.message_invites import parse_calendar_invite
from features.mail.message_leaf_parts import (
    build_attachment_id,
    decode_message_part_text,
    is_attachment_part,
    is_inline_part,
    iter_leaf_parts,
    read_message_part_bytes,
)
from features.mail.message_metadata import (
    build_thread_id,
    extract_references,
    normalize_message_id,
    parse_address_header,
    parse_header_datetime_to_epoch_ms,
)

__all__ = ("parse_message_bytes",)


def parse_message_bytes(
    *,
    message_bytes: bytes,
    remote_mailbox: str | None,
    uidvalidity: int | None,
    uid: int | None,
    uidl: str | None,
    received_at_ms: int,
    unread: bool,
    flagged: bool,
    attachment_identity_key: str,
    snippet_max_chars: int,
) -> JSONDict:
    message = BytesParser(policy=policy.default).parsebytes(message_bytes)
    subject = str(message.get("Subject") or "").strip() or "(no subject)"
    references = extract_references(message)
    in_reply_to_message_id = normalize_message_id(message.get("In-Reply-To"))
    rfc822_message_id = normalize_message_id(message.get("Message-ID"))
    sent_at_ms = parse_header_datetime_to_epoch_ms(message.get("Date"))
    plain_parts: list[str] = []
    html_parts: list[str] = []
    invite_payload: JSONDict | None = None
    parts: list[JSONDict] = []
    attachment_count = 0
    for part_id, part in iter_leaf_parts(message, prefix="1"):
        mime_type = part.get_content_type().strip().lower()
        filename_value = part.get_filename()
        filename = filename_value.strip() if isinstance(filename_value, str) else None
        payload_bytes = read_message_part_bytes(part)
        text_value = decode_message_part_text(part, payload_bytes)
        is_attachment = is_attachment_part(part, filename=filename)
        is_inline = is_inline_part(part, is_attachment=is_attachment)
        attachment_id = None
        if is_attachment:
            attachment_count += 1
            attachment_id = build_attachment_id(
                attachment_identity_key=attachment_identity_key,
                part_id=part_id,
            )
        elif mime_type == "text/plain" and text_value:
            plain_parts.append(text_value)
        elif mime_type == "text/html" and text_value:
            html_parts.append(text_value)
        if mime_type == "text/calendar":
            calendar_invite = parse_calendar_invite(payload_bytes)
            if calendar_invite:
                invite_payload = calendar_invite
        parts.append(
            {
                "part_id": part_id,
                "attachment_id": attachment_id,
                "mime_type": mime_type,
                "filename": filename,
                "is_inline": is_inline,
                "size_bytes": len(payload_bytes),
                "attachment_remote_spec": {"part_id": part_id},
            },
        )
    body_html = "\n\n".join([item for item in html_parts if item.strip()]).strip() or None
    body_text = "\n\n".join([item for item in plain_parts if item.strip()]).strip()
    if not body_text and body_html:
        body_text = extract_html_text_excerpt(
            html_text=body_html,
            max_chars=max(snippet_max_chars * 10, 1_000),
        )
    snippet_source = body_text
    if not snippet_source and body_html:
        snippet_source = extract_html_text_excerpt(
            html_text=body_html,
            max_chars=max(snippet_max_chars, 50),
        )
    snippet = snippet_source[: max(snippet_max_chars, 1)].strip() or subject
    to_addresses = parse_address_header(message.get_all("To", []))
    if not to_addresses:
        to_addresses = []
    return {
        "message": {
            "remote_mailbox": remote_mailbox,
            "uidvalidity": uidvalidity,
            "uid": uid,
            "uidl": uidl,
            "thread_id": build_thread_id(
                references=references,
                in_reply_to_message_id=in_reply_to_message_id,
                rfc822_message_id=rfc822_message_id,
                subject=subject,
            ),
            "rfc822_message_id": rfc822_message_id,
            "in_reply_to_message_id": in_reply_to_message_id,
            "references": references,
            "subject": subject,
            "from": parse_address_header(message.get_all("From", [])),
            "to": to_addresses,
            "cc": parse_address_header(message.get_all("Cc", [])),
            "bcc": parse_address_header(message.get_all("Bcc", [])),
            "sent_at_ms": sent_at_ms,
            "received_at_ms": received_at_ms,
            "snippet": snippet,
            "size_bytes": len(message_bytes),
            "unread": unread,
            "flagged": flagged,
            "has_attachments": attachment_count > 0,
            "attachment_count": attachment_count,
            "invite": invite_payload,
        },
        "body_text": body_text,
        "body_html": body_html,
        "parts": parts,
    }
