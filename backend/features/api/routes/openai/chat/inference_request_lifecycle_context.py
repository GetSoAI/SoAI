"""SoAI - OpenAI chat inference lifecycle context [backend/features/api/routes/openai/chat/inference_request_lifecycle_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.runtime.request_context import RequestContext
from features.api.routes.openai.chat.inference_request_failure_handling import (
    finalize_openai_running_turn_error_noncritical,
    handle_inference_request_failure,
)
from features.api.runtime.openai_execution.contracts import InferenceQuotaContext

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("InferenceRequestLifecycleContext", "build_inference_request_lifecycle_context")


@dataclass(frozen=True, slots=True)
class InferenceRequestLifecycleContext:
    api_context: ApiContext
    request_context: RequestContext
    logger: LoggerProtocol
    api_key_id: str | None
    quota_reservation: JSONDict | None
    quota: InferenceQuotaContext

    async def finalize_claimed_turn_error(
        self,
        *,
        tool_context: MCPToolContext | None,
        error_message: str | None,
        error_type: str | None,
        operation: str,
        log_message: str,
    ) -> None:
        await finalize_openai_running_turn_error_noncritical(
            api_context=self.api_context,
            logger=self.logger,
            context=self.request_context,
            tool_context=tool_context,
            error_message=error_message,
            error_type=error_type,
            operation=operation,
            log_message=log_message,
        )

    async def handle_failure(
        self,
        *,
        tool_context: MCPToolContext | None,
        claimed_agent_turn: bool,
        exception: BaseException,
        log_message: str,
        level: str,
        finalize_log_message: str,
    ) -> None:
        await handle_inference_request_failure(
            api_context=self.api_context,
            logger=self.logger,
            context=self.request_context,
            tool_context=tool_context,
            claimed_agent_turn=claimed_agent_turn,
            api_key_id=self.api_key_id,
            quota_reservation=self.quota_reservation,
            exception=exception,
            log_message=log_message,
            level=level,
            finalize_log_message=finalize_log_message,
        )


def build_inference_request_lifecycle_context(
    *,
    api_context: ApiContext,
    request_context: RequestContext,
    logger: LoggerProtocol,
    api_key_id: str | None,
    quota_reservation: JSONDict | None,
) -> InferenceRequestLifecycleContext:
    return InferenceRequestLifecycleContext(
        api_context=api_context,
        request_context=request_context,
        logger=logger,
        api_key_id=api_key_id,
        quota_reservation=quota_reservation,
        quota=InferenceQuotaContext(
            api_context=api_context,
            key_id=api_key_id,
            reservation=quota_reservation,
            trace_id=request_context.trace_id,
            operation_prefix="api_openai",
        ),
    )
