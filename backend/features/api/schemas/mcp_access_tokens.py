"""SoAI - MCP access token API schemas [backend/features/api/schemas/mcp_access_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, StrictInt, field_validator

from core.validation.strings import require_trimmed_text
from features.api.schemas.shared_validation import require_positive_optional_schema_int

__all__ = ("McpAccessTokenCreatePayload",)


class McpAccessTokenCreatePayload(BaseModel):
    label: str
    expires_at_ms: StrictInt | None = None

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        return require_trimmed_text(value, "Label cannot be empty.")

    @field_validator("expires_at_ms")
    @classmethod
    def validate_expires_at_ms(cls, value: StrictInt | None) -> StrictInt | None:
        require_positive_optional_schema_int(
            value,
            error_message="Expiration timestamp must be positive.",
        )
        return value
