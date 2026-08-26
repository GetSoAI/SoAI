"""SoAI - OpenAI durable execution admission [backend/features/api/runtime/openai_execution/admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.orchestrator.protocols_lifecycle import InferenceAdmissionRequest
from features.api.runtime.openai_execution.contracts import (
    AcceptedOpenAIExecution,
    InferenceLifecycleError,
    InferenceQuotaContext,
    OpenAIExecutionAdmission,
)
from features.api.runtime.openai_quota_reservations import (
    release_token_quota_reservation_if_present,
)
from features.api.runtime.openai_task_failures import handle_task_creation_failure
from features.openai.reasoning_effort_sanitization import (
    sanitize_reasoning_effort_for_model,
)

if TYPE_CHECKING:
    from features.api.runtime.openai_context.internal_protocols import (
        OpenAIApiContextProtocol,
    )

__all__ = ("accept_openai_execution",)

OPENAI_EXECUTION_ADMISSION_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    *RECOVERABLE_EXCEPTIONS,
)


async def _release_quota(quota: InferenceQuotaContext, step: str) -> None:
    await release_token_quota_reservation_if_present(
        quota.api_context,
        quota.key_id,
        quota.reservation,
        trace_id=quota.trace_id,
        operation=f"{quota.operation_prefix}.{step}.quota_release",
    )


async def accept_openai_execution(
    *,
    api_context: OpenAIApiContextProtocol,
    admission: OpenAIExecutionAdmission,
) -> AcceptedOpenAIExecution:
    try:
        sanitized_payload = await sanitize_reasoning_effort_for_model(
            payload=admission.payload,
            model_resolution_service=api_context.dependencies.model_resolution_service,
            model_information_service=api_context.dependencies.model_information_service,
            virtual_model_get=api_context.dependencies.model_virtual_model_service.virtual_model_get,
        )
        receipt = await api_context.dependencies.orchestrator_control.accept_inference_request(
            InferenceAdmissionRequest(
                request_context=admission.context,
                payload=sanitized_payload,
                task_type=admission.task_type,
                user_id=admission.user_id,
                owner_type=admission.owner_type,
                owner_id=admission.owner_id,
                cancellation_id=admission.cancellation_id,
                metadata=admission.metadata,
                request_event_class=admission.request_event_class,
                required_capabilities=tuple(admission.required_capabilities),
                required_modalities=tuple(admission.required_modalities),
                request_source=admission.request_source,
                delivery_mode=admission.delivery_mode,
                task_id=admission.task_id,
                reply_queue=admission.reply_queue,
                attach_reply_queue=admission.attach_reply_queue,
            ),
        )
        if admission.attach_reply_queue and receipt.reply_queue is None:
            missing_reply_queue = StateError(
                "Durable OpenAI execution admission did not return a reply queue.",
            )
            await _release_quota(
                admission.quota,
                "accept_inference_request.missing_reply_queue",
            )
            raise InferenceLifecycleError(
                handle_task_creation_failure(
                    missing_reply_queue,
                    admission.context,
                    f"{admission.quota.operation_prefix}.accept_inference_request",
                    admission.metrics_manager,
                ),
            )
        return AcceptedOpenAIExecution(
            task=receipt.task,
            reply_queue=receipt.reply_queue,
            payload=sanitized_payload,
        )
    except asyncio.CancelledError:
        await _release_quota(admission.quota, "accept_inference_request.cancelled")
        raise
    except OPENAI_EXECUTION_ADMISSION_EXCEPTIONS as exception:
        await _release_quota(admission.quota, "accept_inference_request")
        raise InferenceLifecycleError(
            handle_task_creation_failure(
                exception,
                admission.context,
                f"{admission.quota.operation_prefix}.accept_inference_request",
                admission.metrics_manager,
            ),
        ) from exception
