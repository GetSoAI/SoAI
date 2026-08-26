"""SoAI - Parameter update/delete queue worker for mutation service [backend/models/parameters/mutation/update_queue_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeGuard

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.tasks.action_queue import run_action_queue_processor
from core.tasks.api_events import send_task_complete_event
from core.tasks.failure_events import send_error_event_and_finalize
from core.timing.constants import CONTROL_TIMEOUT_SEC
from core.types.json_value import coerce_json_dict
from models.parameters.mutation.types import (
    DeleteTaskPayload,
    UpdateQueuePayload,
    UpdateTaskPayload,
)

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict

__all__ = (
    "run_parameter_update_queue_worker",
    "signal_update_workers_shutdown",
)

OPERATION_MODELS_PARAMETERS_MUTATION_UPDATE_QUEUE_WORKER_DELETE = (
    "models.parameters.mutation.update_queue_worker.delete"
)
OPERATION_MODELS_PARAMETERS_MUTATION_UPDATE_QUEUE_WORKER_UPDATE = (
    "models.parameters.mutation.update_queue_worker.update"
)


def _is_update_payload(payload: UpdateQueuePayload) -> TypeGuard[UpdateTaskPayload]:
    return "parameters" in payload


def _is_delete_payload(payload: UpdateQueuePayload) -> TypeGuard[DeleteTaskPayload]:
    return "keys" in payload


def _parse_update_payload(payload: UpdateQueuePayload) -> UpdateTaskPayload:
    if not _is_update_payload(payload):
        raise ValidationError("Invalid update payload.")
    parameters = coerce_json_dict(payload.get("parameters"))
    if parameters is None:
        raise ValidationError("Invalid update payload.")
    return {
        "universal_id": payload["universal_id"],
        "parameters": parameters,
        "reply_channel": payload["reply_channel"],
        "order": payload["order"],
    }


def _parse_delete_payload(payload: UpdateQueuePayload) -> DeleteTaskPayload:
    if not _is_delete_payload(payload):
        raise ValidationError("Invalid delete payload.")
    raw_keys = payload.get("keys")
    if not isinstance(raw_keys, list):
        raise ValidationError("Invalid delete payload.")
    keys: list[str] = []
    for item in raw_keys:
        if not isinstance(item, str):
            raise ValidationError("Invalid delete payload.")
        keys.append(item)
    return {
        "universal_id": payload["universal_id"],
        "keys": keys,
        "reply_channel": payload["reply_channel"],
        "order": payload["order"],
    }


async def _execute_update_task(
    *,
    payload: UpdateTaskPayload,
    update_executor: Callable[[str, JSONDict, int | None], Awaitable[None]],
    task_registry: TaskRegistryProtocol,
    logger: LoggerProtocol,
) -> None:
    reply = payload["reply_channel"]
    try:
        await update_executor(
            payload["universal_id"],
            payload["parameters"],
            payload["order"],
        )
        await send_task_complete_event(
            reply,
            "Parameters updated successfully.",
            registry=task_registry,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Error executing parameter update task",
            operation=OPERATION_MODELS_PARAMETERS_MUTATION_UPDATE_QUEUE_WORKER_UPDATE,
        )
        await send_error_event_and_finalize(
            reply,
            str(exception),
            ErrorType.SERVER_ERROR,
            registry=task_registry,
        )


async def _execute_delete_task(
    *,
    payload: DeleteTaskPayload,
    delete_executor: Callable[[str, list[str], int | None], Awaitable[None]],
    task_registry: TaskRegistryProtocol,
    logger: LoggerProtocol,
) -> None:
    reply = payload["reply_channel"]
    try:
        await delete_executor(
            payload["universal_id"],
            payload["keys"],
            payload["order"],
        )
        await send_task_complete_event(
            reply,
            "Parameters deleted successfully.",
            registry=task_registry,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Error executing parameter delete task",
            operation=OPERATION_MODELS_PARAMETERS_MUTATION_UPDATE_QUEUE_WORKER_DELETE,
        )
        await send_error_event_and_finalize(
            reply,
            str(exception),
            ErrorType.SERVER_ERROR,
            registry=task_registry,
        )


async def run_parameter_update_queue_worker(
    *,
    update_queue: asyncio.Queue[tuple[str, UpdateQueuePayload] | None],
    update_executor: Callable[[str, JSONDict, int | None], Awaitable[None]],
    delete_executor: Callable[[str, list[str], int | None], Awaitable[None]],
    task_registry: TaskRegistryProtocol,
    logger: LoggerProtocol,
    shutdown_event: asyncio.Event,
) -> None:
    async def handle_update(_: str, payload: UpdateQueuePayload) -> None:
        await _execute_update_task(
            payload=_parse_update_payload(payload),
            update_executor=update_executor,
            task_registry=task_registry,
            logger=logger,
        )

    async def handle_delete(_: str, payload: UpdateQueuePayload) -> None:
        await _execute_delete_task(
            payload=_parse_delete_payload(payload),
            delete_executor=delete_executor,
            task_registry=task_registry,
            logger=logger,
        )

    await run_action_queue_processor(
        update_queue,
        handlers={"update": handle_update, "delete": handle_delete},
        logger=logger,
        shutdown_event=shutdown_event,
        timeout=1.0,
    )


async def signal_update_workers_shutdown(
    *,
    update_queue: asyncio.Queue[tuple[str, UpdateQueuePayload] | None],
    logger: LoggerProtocol,
    num_workers: int,
) -> None:
    for _ in range(num_workers):
        try:
            await asyncio.wait_for(update_queue.put(None), timeout=CONTROL_TIMEOUT_SEC)
        except TimeoutError:
            logger.warning("Timed out sending shutdown signal to model helper worker")
