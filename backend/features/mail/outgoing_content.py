"""SoAI - Mail outgoing content handling [backend/features/mail/outgoing_content.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import mimetypes
from email.message import EmailMessage
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.filesystem.open_files import open_binary
from core.types.json import JSONValue
from core.validation.strings import require_trimmed_json_text

if TYPE_CHECKING:
    from core.files.database_types import FileCatalogRecordWithPath
    from core.types.json import JSONDict

__all__ = (
    "apply_outgoing_content",
    "require_choice",
)


def apply_outgoing_content(
    *,
    message: EmailMessage,
    mode: str,
    payload: JSONDict,
    base_message: JSONDict | None,
    base_body_text: str | None,
    attachment_records: list[FileCatalogRecordWithPath],
) -> None:
    message["Subject"] = _resolve_subject(mode=mode, payload=payload)
    _apply_reply_headers(message=message, mode=mode, base_message=base_message)
    body_text = require_text(payload.get("body_text"), label="body_text")
    resolved_body_text = _resolve_body_text(
        mode=mode,
        user_body_text=body_text,
        base_message=base_message,
        base_body_text=base_body_text,
    )
    message.set_content(resolved_body_text)
    body_html_value = payload.get("body_html")
    if isinstance(body_html_value, str) and body_html_value.strip():
        message.add_alternative(body_html_value, subtype="html")
    for record in attachment_records:
        _add_attachment(message, record)


def require_choice(value: JSONValue, *, label: str, choices: set[str]) -> str:
    normalized = require_text(value, label=label)
    if normalized not in choices:
        raise ValidationError(f"{label} is invalid.")
    return normalized


def require_text(value: JSONValue, *, label: str) -> str:
    return require_trimmed_json_text(value, error_message=f"{label} is required.")


def supports_draft_mode(payload: JSONDict) -> bool:
    return payload.get("delivery") != "save_draft" or payload.get("protocol") == "imap"


def _resolve_subject(*, mode: str, payload: JSONDict) -> str:
    explicit_subject = require_text(payload.get("subject"), label="subject")
    if mode == "new":
        return explicit_subject
    if mode in {"reply", "reply_all"}:
        if explicit_subject.lower().startswith("re:"):
            return explicit_subject
        return f"Re: {explicit_subject}"
    if explicit_subject.lower().startswith("fwd:"):
        return explicit_subject
    return f"Fwd: {explicit_subject}"


def _apply_reply_headers(
    *,
    message: EmailMessage,
    mode: str,
    base_message: JSONDict | None,
) -> None:
    if mode == "new" or base_message is None:
        return
    message_id_value = base_message.get("rfc822_message_id")
    if isinstance(message_id_value, str) and message_id_value.strip():
        normalized_message_id = message_id_value.strip()
        message["In-Reply-To"] = normalized_message_id
        references = _coerce_reference_headers(base_message)
        if normalized_message_id not in references:
            references.append(normalized_message_id)
        if references:
            message["References"] = " ".join(references)


def _resolve_body_text(
    *,
    mode: str,
    user_body_text: str,
    base_message: JSONDict | None,
    base_body_text: str | None,
) -> str:
    if mode == "new" or base_message is None:
        return user_body_text
    subject_value = base_message.get("subject")
    subject = subject_value.strip() if isinstance(subject_value, str) else "(no subject)"
    quoted_source = (
        base_body_text.strip() if isinstance(base_body_text, str) and base_body_text.strip() else ""
    )
    if not quoted_source:
        snippet_value = base_message.get("snippet")
        quoted_source = (
            snippet_value.strip()
            if isinstance(snippet_value, str) and snippet_value.strip()
            else ""
        )
    if quoted_source:
        quoted_block = "\n".join(
            f"> {line}" if line else ">" for line in quoted_source.splitlines()
        )
    else:
        quoted_block = "> (no cached body)"
    if mode == "forward":
        forwarded_body = quoted_source or "(no cached body)"
        return (
            f"{user_body_text}\n\n---------- Forwarded message ----------\n"
            f"Subject: {subject}\n\n{forwarded_body}"
        )
    return f"{user_body_text}\n\nOn the referenced message about {subject}:\n{quoted_block}"


def _add_attachment(message: EmailMessage, record: FileCatalogRecordWithPath) -> None:
    file_path = record["file_path"]
    with open_binary(file_path, mode="rb") as handle:
        content = handle.read()
    mime_type, _encoding = mimetypes.guess_type(record["filename"])
    if not isinstance(mime_type, str) or "/" not in mime_type:
        mime_type = "application/octet-stream"
    main_type, sub_type = mime_type.split("/", 1)
    message.add_attachment(
        content,
        maintype=main_type,
        subtype=sub_type,
        filename=record["filename"],
    )


def _coerce_reference_headers(base_message: JSONDict) -> list[str]:
    references_value = base_message.get("references")
    if not isinstance(references_value, list):
        return []
    references: list[str] = []
    for item in references_value:
        if isinstance(item, str) and item.strip():
            references.append(item.strip())
    return references
