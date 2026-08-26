"""SoAI - MCP worker processing failure classification helpers [backend/mcp/worker/processing/job_failure_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError
from core.types.json_value import filter_json_mapping

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "FAILED_FAILURE_DETAILS",
    "resolve_document_id",
    "resolve_error_code",
    "resolve_failure_details",
)

UNREADABLE_FAILURE_DETAILS = "unreadable"
FAILED_FAILURE_DETAILS = "failed"


def resolve_document_id(document_id: str | None, job_payload: JSONDict | None) -> str:
    normalized_document_id = str(document_id or "").strip()
    if normalized_document_id:
        return normalized_document_id
    if job_payload is None:
        return ""
    return str(job_payload.get("document_id") or "").strip()


def resolve_failure_details(error: SoAIError) -> str:
    details = filter_json_mapping(error.details)
    if details.get("rag_status_details") == UNREADABLE_FAILURE_DETAILS:
        return UNREADABLE_FAILURE_DETAILS
    return FAILED_FAILURE_DETAILS


def resolve_error_code(error: SoAIError) -> int:
    code = int(error.http_status)
    if code < 100 or code > 599:
        return 500
    return code
