"""SoAI - Conversation input worker execution [backend/app/background/conversation_input_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ConflictError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.validation.record_fields import require_int, require_non_empty_str
from features.api.runtime.chat_stream_registry import ChatStreamReservation
from features.chat.conversation_input_cancellation_admission import (
    terminalize_claimed_input_if_cancelled,
)
from features.chat.conversation_input_claim_execution import (
    execute_claimed_conversation_input_preparation,
)
from features.chat.conversation_input_runtime import require_conversation_input_identity

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("run_conversation_input_worker",)

OPERATION_WORKER = "app.background.conversation_input_dispatcher.worker"
IDLE_WAIT_SECONDS = 0.25
TERMINALIZATION_BACKOFF_MAX_SECONDS = 30.0


async def _wait_for_work(wake_event: asyncio.Event) -> None:
    try:
        await asyncio.wait_for(wake_event.wait(), timeout=IDLE_WAIT_SECONDS)
    except TimeoutError:
        return
    finally:
        wake_event.clear()


async def _terminalize_uncertain_input(
    api_dependencies: ApiDependencies,
    *,
    claimed: JSONDict,
    claim_owner: str,
    server_boot_id: str,
    shutdown_event: asyncio.Event,
    logger: LoggerProtocol,
) -> None:
    attempt = 0
    while not shutdown_event.is_set():
        try:
            await api_dependencies.database_input_execution.terminalize_input(
                input_id=require_non_empty_str(
                    claimed.get("input_id"),
                    label="Conversation input id",
                    build_error=StateError,
                ),
                claim_generation=require_int(
                    claimed.get("claim_generation"),
                    label="Conversation input claim generation",
                    build_error=StateError,
                    minimum=1,
                ),
                claim_owner=claim_owner,
                server_boot_id=server_boot_id,
                terminal_state="effect_unknown",
                terminal_code="dispatcher_exit_effect_unknown",
                terminal_args={},
            )
            return
        except ConflictError:
            return
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Conversation input terminalization will be retried.",
                operation=OPERATION_WORKER,
                level="warning",
            )
        delay = compute_exponential_backoff_seconds(
            attempt,
            base_seconds=1.0,
            maximum_seconds=TERMINALIZATION_BACKOFF_MAX_SECONDS,
            jitter_ratio=0.2,
        )
        attempt += 1
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=delay)
        except TimeoutError:
            continue


async def _claim_reservable_input(
    api_dependencies: ApiDependencies,
    *,
    claim_owner: str,
    server_boot_id: str,
) -> tuple[JSONDict, ChatStreamReservation] | None:
    excluded_conversation_ids: set[str] = set()
    while True:
        claimed = await api_dependencies.database_input_execution.claim_next_input(
            claim_owner=claim_owner,
            server_boot_id=server_boot_id,
            excluded_conversation_ids=tuple(sorted(excluded_conversation_ids)),
        )
        if claimed is None:
            return None
        input_id, conv_id, user_id, claim_generation = require_conversation_input_identity(
            claimed,
        )
        request_id_value = claimed.get("request_id")
        reservation = ChatStreamReservation(
            user_id=user_id,
            conv_id=conv_id,
            request_id=(
                request_id_value
                if isinstance(request_id_value, str) and request_id_value.strip()
                else f"chat_{input_id}"
            ),
        )
        if await api_dependencies.chat_stream_registry.try_reserve(reservation):
            return claimed, reservation
        await api_dependencies.database_input_execution.defer_claim(
            input_id=input_id,
            claim_generation=claim_generation,
            claim_owner=claim_owner,
            server_boot_id=server_boot_id,
        )
        excluded_conversation_ids.add(conv_id)


async def run_conversation_input_worker(
    api_dependencies: ApiDependencies,
    *,
    worker_index: int,
    server_boot_id: str,
    shutdown_event: asyncio.Event,
    wake_event: asyncio.Event,
    logger: LoggerProtocol,
) -> None:
    claim_owner = f"worker-{worker_index}"
    while not shutdown_event.is_set():
        claim_result = await _claim_reservable_input(
            api_dependencies,
            claim_owner=claim_owner,
            server_boot_id=server_boot_id,
        )
        if claim_result is None:
            await _wait_for_work(wake_event)
            continue
        claimed, reservation = claim_result
        try:
            execution_task = create_ephemeral_task(
                execute_claimed_conversation_input_preparation(
                    api_dependencies,
                    claimed=claimed,
                    claim_owner=claim_owner,
                    server_boot_id=server_boot_id,
                    logger=logger,
                ),
                name=f"conversation-input-{claimed.get('input_id', 'unknown')}",
            )
            api_dependencies.application_control.track_background_task(execution_task)
            await execution_task
        except asyncio.CancelledError:
            if shutdown_event.is_set():
                raise
            try:
                terminalized = await terminalize_claimed_input_if_cancelled(
                    api_dependencies,
                    claimed=claimed,
                    input_id=require_non_empty_str(
                        claimed.get("input_id"),
                        label="Conversation input id",
                        build_error=StateError,
                    ),
                    claim_generation=require_int(
                        claimed.get("claim_generation"),
                        label="Conversation input claim generation",
                        build_error=StateError,
                        minimum=1,
                    ),
                    claim_owner=claim_owner,
                    server_boot_id=server_boot_id,
                )
            except ConflictError:
                terminalized = True
            if not terminalized:
                await _terminalize_uncertain_input(
                    api_dependencies,
                    claimed=claimed,
                    claim_owner=claim_owner,
                    server_boot_id=server_boot_id,
                    shutdown_event=shutdown_event,
                    logger=logger,
                )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Conversation input worker failed.",
                operation=OPERATION_WORKER,
                level="error",
                details={"worker_index": worker_index},
            )
            await _terminalize_uncertain_input(
                api_dependencies,
                claimed=claimed,
                claim_owner=claim_owner,
                server_boot_id=server_boot_id,
                shutdown_event=shutdown_event,
                logger=logger,
            )
        finally:
            await api_dependencies.chat_stream_registry.release_reservation(reservation)
            wake_event.set()
