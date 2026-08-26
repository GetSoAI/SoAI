"""SoAI - Shared OpenAI model context resolution [backend/features/openai/model_context_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.models.reference_resolution import (
    resolve_context_window_tokens_for_reference,
    resolve_model_reference,
)

if TYPE_CHECKING:
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.orchestrator.routing_config import VirtualModelConfig

__all__ = ("resolve_context_window_tokens_for_request_model",)


async def resolve_context_window_tokens_for_request_model(
    *,
    model_name: str,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    virtual_model_get: (
        Callable[[str], Awaitable[VirtualModelConfig | None] | VirtualModelConfig | None] | None
    ) = None,
) -> int | None:
    reference = await resolve_model_reference(
        model_name=model_name,
        model_resolution_service=model_resolution_service,
        virtual_model_get=virtual_model_get,
    )
    if reference is None:
        return None
    return await resolve_context_window_tokens_for_reference(
        reference=reference,
        model_information_service=model_information_service,
    )
