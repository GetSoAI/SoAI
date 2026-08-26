"""SoAI - WebUI conversation attachment request validation [backend/features/api/routes/webui/conversation_attachments/request_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.validation.strings import require_bounded_trimmed_text

__all__ = (
    "require_attachment_request_id",
    "require_attachment_source",
)


def _require_short_text(value: str, *, field_name: str, max_length: int) -> str:
    return require_bounded_trimmed_text(
        value,
        type_message=f"{field_name} must be a string.",
        empty_message=f"{field_name} is required.",
        max_length=max_length,
        max_length_message=f"{field_name} is too long.",
        nul_message=f"{field_name} must not contain NUL bytes.",
    )


def require_attachment_request_id(value: str) -> str:
    return _require_short_text(value, field_name="client_request_id", max_length=128)


def require_attachment_source(value: str) -> str:
    return _require_short_text(value, field_name="source", max_length=64)
