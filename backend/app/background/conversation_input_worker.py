"""SoAI - Conversation input worker execution [backend/app/background/conversation_input_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ConflictError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.conversation_publication import (
    publish_conversation_updated_and_message_saved,
)
from core.logging.trace import get_logger
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.validation.record_fields import require_int, require_json_object, require_non_empty_str
from features.api.routes.webui.conversation_input_queue_delivery_events import (
    publish_knowledge_events_from_delivery_result,
)
from features.api.routes.webui.conversation_input_queue_events import (
    publish_current_input_queue_changed,
)
from features.chat.conversation_input_execution import (
    execute_claimed_conversation_input,
)
from features.messaging.input_media_ingestion import prepare_messaging_input_media

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("run_conversation_input_worker",)

OPERATION_WORKER = "app.background.conversation_input_dispatcher.worker"
LOGGER_NAME = "SoAI.app.background.conversation_input_worker"
IDLE_WAIT_SECONDS = 0.25
TERMINALIZATION_BACKOFF_MAX_SECONDS = 30.0


async def _wait_for_work(wake_event: asyncio.Event) -> None:
    try:
        await asyncio.wait_for(wake_event.wait(), timeout=IDLE_WAIT_SECONDS)
    except TimeoutError:
        return
    finally:
        wake_event.clear()


async def _publish_materialization(
    api_dependencies: ApiDependencies,
    materialized: JSONDict,
) -> None:
    user_id = require_int(
        materialized.get("user_id"),
        label="Materialized conversation input owner",
        build_error=StateError,
        minimum=1,
    )
    conv_id = require_non_empty_str(
        materialized.get("conv_id"),
        label="Materialized conversation input conversation",
        build_error=StateError,
    )
    if materialized.get("was_materialized") is True:
        message_count = require_int(
            materialized.get("message_count"),
            label="Materialized conversation input message count",
            build_error=StateError,
            minimum=0,
        )
        last_modified_at_ms = require_int(
            materialized.get("conversation_last_modified_at_ms"),
            label="Materialized conversation input revision",
            build_error=StateError,
            minimum=1,
        )
        conversation_title_value = materialized.get("conversation_title")
        conversation_title = (
            require_non_empty_str(
                conversation_title_value,
                label="Materialized conversation input title",
                build_error=StateError,
            )
            if conversation_title_value is not None
            else None
        )
        publication = publish_conversation_updated_and_message_saved(
            api_dependencies.event_bus,
            user_id=user_id,
            conv_id=conv_id,
            message_count=message_count,
            last_modified_at_ms=last_modified_at_ms,
            message=require_json_object(
                materialized.get("materialized_message"),
                label="Materialized conversation input message",
                build_error=StateError,
                invalid_message="Materialized conversation input message is invalid.",
            ),
            title=conversation_title,
        )
        try:
            await publication
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                coerce_to_soai_error(exception, operation=OPERATION_WORKER),
                message="Conversation input materialization event publication failed.",
                operation=OPERATION_WORKER,
                level="debug",
                details={"user_id": user_id, "conv_id": conv_id},
            )
        await publish_knowledge_events_from_delivery_result(api_dependencies, materialized)
    await publish_current_input_queue_changed(
        api_dependencies=api_dependencies,
        user_id=user_id,
        conv_id=conv_id,
    )


async def _execute_claimed_input(
    api_dependencies: ApiDependencies,
    *,
    claimed: JSONDict,
    claim_owner: str,
    server_boot_id: str,
) -> None:
    input_id = require_non_empty_str(
        claimed.get("input_id"),
        label="Conversation input id",
        build_error=StateError,
    )
    claim_generation = require_int(
        claimed.get("claim_generation"),
        label="Conversation input claim generation",
        build_error=StateError,
        minimum=1,
    )
    media_preparation = await prepare_messaging_input_media(
        api_dependencies,
        input_record=claimed,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
    )
    if media_preparation.status == "failed":
        terminal_code = media_preparation.terminal_code
        if terminal_code is None:
            raise StateError("Messaging media failure is missing a terminal code.")
        terminal = await api_dependencies.database_input_queue.terminalize_input(
            input_id=input_id,
            claim_generation=claim_generation,
            claim_owner=claim_owner,
            server_boot_id=server_boot_id,
            terminal_state="failed",
            terminal_code=terminal_code,
            terminal_args={},
        )
        await publish_current_input_queue_changed(
            api_dependencies=api_dependencies,
            user_id=require_int(
                terminal.get("user_id"),
                label="Failed Messaging media input owner",
                build_error=StateError,
                minimum=1,
            ),
            conv_id=require_non_empty_str(
                terminal.get("conv_id"),
                label="Failed Messaging media input conversation",
                build_error=StateError,
            ),
        )
        return
    claimed = media_preparation.input_record
    materialized = await api_dependencies.database_input_queue.materialize_claimed_input(
        input_id=input_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
    )
    materialized["model_settings"] = (
        await api_dependencies.database_input_queue.get_input_execution_settings(
            input_id=input_id,
        )
    )
    await _publish_materialization(api_dependencies, materialized)
    await execute_claimed_conversation_input(
        api_dependencies,
        input_record=materialized,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
    )


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
            await api_dependencies.database_input_queue.terminalize_input(
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
        claimed = await api_dependencies.database_input_queue.claim_next_input(
            claim_owner=claim_owner,
            server_boot_id=server_boot_id,
        )
        if claimed is None:
            await _wait_for_work(wake_event)
            continue
        try:
            await _execute_claimed_input(
                api_dependencies,
                claimed=claimed,
                claim_owner=claim_owner,
                server_boot_id=server_boot_id,
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
            wake_event.set()
