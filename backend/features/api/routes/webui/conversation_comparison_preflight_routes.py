"""SoAI - HTTP endpoints for comparison turn preflight [backend/features/api/routes/webui/conversation_comparison_preflight_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from core.timing.epoch import epoch_ms
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import (
    raise_invalid_request,
    raise_not_found,
)
from features.api.schemas.comparison_turns import (
    ComparisonTurnPreflightRequest,
    ComparisonTurnPreflightResponse,
    ComparisonTurnPreflightVariant,
)

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post("/conversations/{conv_id}/comparison-turns/preflight")
    async def preflight_comparison_turn(
        request: Request,
        conv_id: str,
        payload: ComparisonTurnPreflightRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        effective_models = [payload.primary_model_id, *payload.comparison_model_ids]
        resolved_universal_ids: list[str] = []
        for model_id in effective_models:
            universal_id = await api_context.dependencies.model_resolution_service.model_resolve_to_universal_id(
                model_id,
            )
            if universal_id is None:
                raise_invalid_request(
                    request,
                    f"Comparison preflight failed to resolve model {model_id}.",
                )
            exists = await api_context.dependencies.model_resolution_service.model_check_exists(
                universal_id,
            )
            if not exists:
                raise_invalid_request(
                    request,
                    f"Comparison preflight model is unavailable: {model_id}.",
                )
            resolved_universal_ids.append(universal_id)
        message_count = await api_context.dependencies.database_messages.count_messages(
            conv_id,
            current_user["id"],
        )
        if message_count is None:
            raise_not_found(
                request,
                "Conversation not found or you do not have permission to access it.",
            )
        latest_timestamp = (
            await api_context.dependencies.database_messages.get_latest_message_timestamp(
                conv_id,
                current_user["id"],
            )
        )
        latest_or_zero = 0 if latest_timestamp is None else int(latest_timestamp)
        minimum_assistant_turn_at_ms = payload.minimum_assistant_turn_at_ms
        base_timestamp = max(
            int(epoch_ms()),
            latest_or_zero + 1,
            0 if minimum_assistant_turn_at_ms is None else int(minimum_assistant_turn_at_ms),
        )
        variants: list[ComparisonTurnPreflightVariant] = []
        for variant_index, resolved_id in enumerate(resolved_universal_ids):
            assistant_at_ms = base_timestamp + int(variant_index)
            variants.append(
                ComparisonTurnPreflightVariant(
                    model_variant_index=int(variant_index),
                    requested_model_id=effective_models[variant_index],
                    resolved_model_id=resolved_id,
                    assistant_at_ms=int(assistant_at_ms),
                ),
            )
        response = ComparisonTurnPreflightResponse(
            assistant_turn_at_ms=int(base_timestamp),
            variants=variants,
        )
        return JSONResponse(content=response.model_dump(exclude_none=True))
