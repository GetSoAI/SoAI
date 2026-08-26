"""SoAI - Knowledge prompt delivery finalization [backend/features/api/runtime/knowledge_prompt_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.rag.knowledge_prompt_types import KnowledgePromptDeliveryClaim
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "commit_knowledge_prompt_claim_noncritical",
    "release_knowledge_prompt_claim_noncritical",
)

LOGGER_NAME = "SoAI.features.api.knowledge_prompt_delivery"
OPERATION_COMMIT = "webui_ws_chat_stream.knowledge_prompt.commit"
OPERATION_RELEASE = "webui_ws_chat_stream.knowledge_prompt.release"
DELIVERY_EXCEPTIONS: tuple[type[Exception], ...] = (SoAIError, *RECOVERABLE_EXCEPTIONS)


async def commit_knowledge_prompt_claim_noncritical(
    *,
    api_dependencies: ApiDependencies,
    claim: KnowledgePromptDeliveryClaim | None,
    logger: LoggerProtocol | None,
    trace_id: str | None,
) -> None:
    if claim is None:
        return
    try:
        await api_dependencies.database_knowledge_prompt_state.commit_active_claim(
            conv_id=claim.conv_id,
            user_id=claim.user_id,
            claim_id=claim.claim_id,
            request_id=claim.request_id,
            event_ceiling_id=claim.event_ceiling_id,
            state_signature=claim.state_signature,
            delivered_at_ms=int(epoch_ms()),
        )
    except DELIVERY_EXCEPTIONS as exception:
        resolved_logger = logger if logger is not None else get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(exception, operation=OPERATION_COMMIT)
        log_exception(
            resolved_logger,
            coerced,
            message="Failed to commit Knowledge prompt delivery claim.",
            trace_id=trace_id,
            operation=OPERATION_COMMIT,
            level="warning",
        )


async def release_knowledge_prompt_claim_noncritical(
    *,
    api_dependencies: ApiDependencies,
    claim: KnowledgePromptDeliveryClaim | None,
    logger: LoggerProtocol | None,
    trace_id: str | None,
) -> None:
    if claim is None:
        return
    try:
        await api_dependencies.database_knowledge_prompt_state.release_active_claim(
            conv_id=claim.conv_id,
            user_id=claim.user_id,
            claim_id=claim.claim_id,
            request_id=claim.request_id,
        )
    except DELIVERY_EXCEPTIONS as exception:
        resolved_logger = logger if logger is not None else get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(exception, operation=OPERATION_RELEASE)
        log_exception(
            resolved_logger,
            coerced,
            message="Failed to release Knowledge prompt delivery claim.",
            trace_id=trace_id,
            operation=OPERATION_RELEASE,
            level="warning",
        )
