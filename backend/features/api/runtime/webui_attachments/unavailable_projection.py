"""SoAI - Unavailable attachment provider projection [backend/features/api/runtime/webui_attachments/unavailable_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.attachment_content_validation import (
    validate_soai_file_unavailable_content_part,
    validate_soai_knowledge_unavailable_content_part,
)
from features.api.runtime.webui_attachments.provider_text_rendering import (
    sanitize_provider_text_field,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("project_unavailable_attachment_for_provider",)


def project_unavailable_attachment_for_provider(part: JSONDict) -> JSONDict | None:
    part_type = part.get("type")
    if part_type == "soai_file_unavailable":
        canonical = validate_soai_file_unavailable_content_part(part)
        filename = sanitize_provider_text_field(str(canonical["filename"])) or "attachment"
        return {"type": "text", "text": f"Unavailable attachment: {filename}."}
    if part_type == "soai_knowledge_unavailable":
        canonical = validate_soai_knowledge_unavailable_content_part(part)
        title = sanitize_provider_text_field(str(canonical["title"])) or "knowledge"
        return {
            "type": "text",
            "text": f"Unavailable knowledge attachment: {title}.",
        }
    return None
