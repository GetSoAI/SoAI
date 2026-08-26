"""SoAI - WebUI conversation attachment response payloads [backend/features/api/routes/webui/conversation_attachments/payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("serialize_physical_attachment",)


def _quote_path_segment(value: str) -> str:
    return quote(value, safe="")


def serialize_physical_attachment(row: JSONDict) -> JSONDict:
    attachment_id = str(row.get("attachment_id") or "")
    conv_id = str(row.get("conv_id") or "")
    preview_path = (
        f"/api/v1/webui/conversations/{_quote_path_segment(conv_id)}"
        f"/attachments/{_quote_path_segment(attachment_id)}/content?download=0"
    )
    download_path = (
        f"/api/v1/webui/conversations/{_quote_path_segment(conv_id)}"
        f"/attachments/{_quote_path_segment(attachment_id)}/content?download=1"
    )
    payload: JSONDict = {
        "client_attachment_id": row.get("client_attachment_id"),
        "attachment_id": row.get("attachment_id"),
        "file_id": row.get("file_id"),
        "filename": row.get("filename"),
        "mime_type": row.get("mime_type"),
        "size_bytes": row.get("size_bytes"),
        "preview_type": row.get("preview_type"),
        "provider_mode": row.get("provider_mode"),
        "provider_text_truncated": row.get("provider_text_truncated"),
        "parse_state": row.get("parse_state"),
        "parse_error": row.get("parse_error"),
        "created_at_ms": row.get("created_at_ms"),
        "updated_at_ms": row.get("updated_at_ms"),
        "attachment_revision": row.get("attachment_revision"),
        "state": row.get("state"),
        "preview_url": preview_path,
        "download_url": download_path,
    }
    return payload
