"""SoAI - OpenAI Responses provider error details [backend/features/api/routes/openai/responses/provider_error_details.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("ResponsesProviderErrorDetails", "extract_provider_error_details")


@dataclass(frozen=True, slots=True)
class ResponsesProviderErrorDetails:
    message: str
    code: str


def _coerce_error_text(value: JSONValue, *, default: str) -> str:
    text = value.strip() if isinstance(value, str) else ""
    return text or default


def extract_provider_error_details(error_payload: JSONDict) -> ResponsesProviderErrorDetails:
    return ResponsesProviderErrorDetails(
        message="Upstream provider request failed.",
        code=_coerce_error_text(
            error_payload.get("code"),
            default="server_error",
        ),
    )
