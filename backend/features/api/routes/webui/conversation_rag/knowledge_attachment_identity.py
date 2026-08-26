"""SoAI - WebUI RAG knowledge attachment identity validation [backend/features/api/routes/webui/conversation_rag/knowledge_attachment_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("require_knowledge_attachment_id",)


def require_knowledge_attachment_id(summary: JSONDict) -> str:
    value = summary.get("knowledge_attachment_id")
    knowledge_attachment_id = coerce_optional_trimmed_str(value if isinstance(value, str) else None)
    if knowledge_attachment_id is None:
        raise StateError("Knowledge attachment id is invalid.")
    return knowledge_attachment_id
