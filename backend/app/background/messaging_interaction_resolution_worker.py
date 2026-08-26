"""SoAI - Durable Messaging interaction resolution worker [backend/app/background/messaging_interaction_resolution_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.tasks.task_cancellation import cancel
from features.api.routes.webui.conversation_input_queue_events import (
    publish_current_input_queue_changed,
)
from features.chat.interaction_service import (
    ConversationInteractionResolutionDependencies,
    resolve_interaction,
)

if TYPE_CHECKING:
    from core.messaging.protocols import DatabaseMessagingIngressProtocol
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "MessagingInteractionResolutionWorker",
    "MessagingInteractionResolutionWorkerDependencies",
)

LOGGER_NAME = "SoAI.app.background.messaging_interaction_resolution_worker"
RESOLUTION_BATCH_SIZE = 100
RETRY_WARNING_INTERVAL_SECONDS = 60.0
OPERATION_RECONCILE = "messaging_interaction_resolution.reconcile"
OPERATION_TIMEOUT = "messaging_interaction_resolution.timeout"


@dataclass(frozen=True, slots=True)
class MessagingInteractionResolutionWorkerDependencies:
    api_dependencies: ApiDependencies
    database_ingress: DatabaseMessagingIngressProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MessagingInteractionResolutionWorkerDependencies",
            api_dependencies=self.api_dependencies,
            database_ingress=self.database_ingress,
        )


class MessagingInteractionResolutionWorker:
    def __init__(self, deps: MessagingInteractionResolutionWorkerDependencies) -> None:
        self._deps = deps
        self._retry_logger = RateLimitedLogger(
            interval_seconds=RETRY_WARNING_INTERVAL_SECONDS,
        )

    def _retry_details(self, details: JSONDict) -> JSONDict | None:
        should_emit, suppressed_count = self._retry_logger.should_emit()
        if not should_emit:
            return None
        retry_details = dict(details)
        retry_details["suppressed_count"] = suppressed_count
        return retry_details

    async def _resolve(self, ingress_id: str) -> bool:
        resolution = await self._deps.database_ingress.get_interaction_resolution(ingress_id)
        if resolution is None:
            return False
        api_dependencies = self._deps.api_dependencies
        await resolve_interaction(
            ConversationInteractionResolutionDependencies(
                task_registry=api_dependencies.task_registry,
                database_notifications=api_dependencies.database_notifications,
            ),
            conv_id=resolution.conv_id,
            task_id=resolution.task_id,
            user_id=resolution.user_id,
            interaction_type=resolution.interaction_type,
            payload=resolution.payload,
            checkpoint_generation=resolution.checkpoint_generation,
        )
        await publish_current_input_queue_changed(
            api_dependencies=api_dependencies,
            user_id=resolution.user_id,
            conv_id=resolution.conv_id,
        )
        return True

    async def _resolve_timeout(
        self,
        *,
        task_id: str,
        conv_id: str,
        user_id: int,
        interaction_type: str,
        checkpoint_generation: int,
    ) -> None:
        api_dependencies = self._deps.api_dependencies
        payload: JSONDict = (
            {"action": "deny", "remember": False}
            if interaction_type == "tool_approval"
            else {"action": "cancel"}
        )
        await resolve_interaction(
            ConversationInteractionResolutionDependencies(
                task_registry=api_dependencies.task_registry,
                database_notifications=api_dependencies.database_notifications,
            ),
            conv_id=conv_id,
            task_id=task_id,
            user_id=user_id,
            interaction_type=interaction_type,
            payload=payload,
            checkpoint_generation=checkpoint_generation,
        )
        await publish_current_input_queue_changed(
            api_dependencies=api_dependencies,
            user_id=user_id,
            conv_id=conv_id,
        )

    async def _cancel_unresolvable(
        self,
        *,
        task_id: str,
        conv_id: str,
        user_id: int,
    ) -> None:
        api_dependencies = self._deps.api_dependencies
        cancelled = await cancel(api_dependencies.task_registry, task_id)
        if cancelled is None:
            raise StateError("Messaging interaction task is unavailable for cancellation.")
        await publish_current_input_queue_changed(
            api_dependencies=api_dependencies,
            user_id=user_id,
            conv_id=conv_id,
        )

    async def reconcile(self) -> int:
        resolutions = await self._deps.database_ingress.list_interaction_resolutions(
            limit=RESOLUTION_BATCH_SIZE,
        )
        resolved_count = 0
        for resolution in resolutions:
            try:
                if await self._resolve(resolution.ingress_id):
                    resolved_count += 1
            except (ConflictError, StateError, ValidationError):
                await self._deps.database_ingress.fail_interaction_route(
                    route_id=resolution.route_id,
                    diagnostic_code="interaction_resolution_invalid",
                )
                await self._cancel_unresolvable(
                    task_id=resolution.task_id,
                    conv_id=resolution.conv_id,
                    user_id=resolution.user_id,
                )
                resolved_count += 1
            except RECOVERABLE_EXCEPTIONS as exception:
                retry_details = self._retry_details(
                    {
                        "ingress_id": resolution.ingress_id,
                        "route_id": resolution.route_id,
                        "task_id": resolution.task_id,
                    },
                )
                if retry_details is not None:
                    log_handled_exception(
                        get_logger(LOGGER_NAME),
                        exception,
                        message="Messaging interaction resolution will be retried.",
                        operation=OPERATION_RECONCILE,
                        level="warning",
                        details=retry_details,
                    )
        timeouts = await self._deps.database_ingress.claim_expired_interactions(
            limit=RESOLUTION_BATCH_SIZE,
        )
        for timeout in timeouts:
            try:
                await self._resolve_timeout(
                    task_id=timeout.task_id,
                    conv_id=timeout.conv_id,
                    user_id=timeout.user_id,
                    interaction_type=timeout.interaction_type,
                    checkpoint_generation=timeout.checkpoint_generation,
                )
                resolved_count += 1
            except (ConflictError, StateError, ValidationError):
                await self._deps.database_ingress.fail_interaction_route(
                    route_id=timeout.route_id,
                    diagnostic_code="interaction_timeout_resolution_invalid",
                )
                await self._cancel_unresolvable(
                    task_id=timeout.task_id,
                    conv_id=timeout.conv_id,
                    user_id=timeout.user_id,
                )
                resolved_count += 1
            except RECOVERABLE_EXCEPTIONS as exception:
                retry_details = self._retry_details(
                    {
                        "route_id": timeout.route_id,
                        "task_id": timeout.task_id,
                    },
                )
                if retry_details is not None:
                    log_handled_exception(
                        get_logger(LOGGER_NAME),
                        exception,
                        message="Messaging interaction timeout resolution will be retried.",
                        operation=OPERATION_TIMEOUT,
                        level="warning",
                        details=retry_details,
                    )
        return resolved_count
