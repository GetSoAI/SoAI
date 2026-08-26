"""SoAI - Responses token count boundary validation [backend/features/api/routes/openai/responses/token_count_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.runtime.errors import raise_payload_too_large

if TYPE_CHECKING:
    from core.openai.token_accounting import PromptOccupancy
    from core.runtime.protocols import ConnectionProtocol

__all__ = ("require_complete_responses_input_token_count",)


def require_complete_responses_input_token_count(
    request: ConnectionProtocol,
    occupancy: PromptOccupancy,
) -> int:
    if occupancy.capped:
        raise_payload_too_large(
            request,
            "Input exceeds the supported token-counting limit.",
            error_type="payload_too_large",
        )
    return occupancy.prompt_tokens
