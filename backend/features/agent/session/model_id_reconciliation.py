"""SoAI - Agent request model reconciliation [backend/features/agent/session/model_id_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.models.reference_resolution import resolve_model_reference
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.models.protocols import ModelResolutionServiceProtocol
    from core.orchestrator.routing_config import VirtualModelConfig

__all__ = ("reconcile_agent_request_model",)


async def _resolve_agent_model_routing_key(
    *,
    candidate: str,
    model_resolution_service: ModelResolutionServiceProtocol,
    virtual_model_get: (
        Callable[[str], Awaitable[VirtualModelConfig | None] | VirtualModelConfig | None] | None
    ),
) -> str | None:
    reference = await resolve_model_reference(
        model_name=candidate,
        model_resolution_service=model_resolution_service,
        virtual_model_get=virtual_model_get,
    )
    if reference is None:
        return None
    if not reference.is_enabled:
        raise ValidationError(f"Model is disabled: {candidate}")
    return reference.routing_key


async def reconcile_agent_request_model(
    *,
    request_model: str | None,
    conversation_model: str | None,
    comparison_models: tuple[str, ...] = (),
    model_resolution_service: ModelResolutionServiceProtocol,
    virtual_model_get: (
        Callable[[str], Awaitable[VirtualModelConfig | None] | VirtualModelConfig | None] | None
    ),
) -> str | None:
    normalized_request = coerce_optional_trimmed_str(request_model)
    normalized_conversation = coerce_optional_trimmed_str(conversation_model)
    if normalized_request is None and normalized_conversation is None:
        return None
    if normalized_request is not None and normalized_conversation is None:
        resolved = await _resolve_agent_model_routing_key(
            candidate=normalized_request,
            model_resolution_service=model_resolution_service,
            virtual_model_get=virtual_model_get,
        )
        if resolved is None:
            raise ValidationError(f"Unknown model: {normalized_request}")
        return resolved
    if normalized_request is None and normalized_conversation is not None:
        resolved = await _resolve_agent_model_routing_key(
            candidate=normalized_conversation,
            model_resolution_service=model_resolution_service,
            virtual_model_get=virtual_model_get,
        )
        if resolved is None:
            raise ValidationError(f"Unknown model: {normalized_conversation}")
        return resolved
    request_candidate = normalized_request
    conversation_candidate = normalized_conversation
    if request_candidate is None or conversation_candidate is None:
        raise ValidationError(
            "Selected model mismatch between request payload and conversation settings.",
        )
    if request_candidate == conversation_candidate:
        resolved = await _resolve_agent_model_routing_key(
            candidate=request_candidate,
            model_resolution_service=model_resolution_service,
            virtual_model_get=virtual_model_get,
        )
        if resolved is None:
            raise ValidationError(f"Unknown model: {request_candidate}")
        return resolved
    resolved_request = await _resolve_agent_model_routing_key(
        candidate=request_candidate,
        model_resolution_service=model_resolution_service,
        virtual_model_get=virtual_model_get,
    )
    if resolved_request is None:
        raise ValidationError(f"Unknown model: {request_candidate}")
    resolved_conversation = await _resolve_agent_model_routing_key(
        candidate=conversation_candidate,
        model_resolution_service=model_resolution_service,
        virtual_model_get=virtual_model_get,
    )
    if resolved_conversation is None:
        raise ValidationError(f"Unknown model: {conversation_candidate}")
    comparison_candidates = [
        candidate.strip()
        for candidate in comparison_models
        if isinstance(candidate, str) and candidate.strip()
    ]
    resolved_comparison_candidates: list[str] = []
    for candidate in comparison_candidates:
        resolved_candidate = await _resolve_agent_model_routing_key(
            candidate=candidate,
            model_resolution_service=model_resolution_service,
            virtual_model_get=virtual_model_get,
        )
        if resolved_candidate is None:
            raise ValidationError(f"Unknown comparison model: {candidate}")
        resolved_comparison_candidates.append(resolved_candidate)
    if (
        isinstance(resolved_request, str)
        and isinstance(resolved_conversation, str)
        and resolved_request
        and resolved_conversation
        and resolved_request == resolved_conversation
    ):
        return resolved_request
    if resolved_request in resolved_comparison_candidates:
        return resolved_request
    raise ValidationError(
        "Selected model mismatch between request payload and conversation settings.",
        details={
            "request_model": normalized_request,
            "conversation_model": normalized_conversation,
            "resolved_request_model": resolved_request,
            "resolved_conversation_model": resolved_conversation,
            "comparison_models": comparison_candidates,
            "resolved_comparison_models": resolved_comparison_candidates,
        },
    )
