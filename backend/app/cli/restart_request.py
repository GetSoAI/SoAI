"""SoAI - CLI lifecycle request file coordination [backend/app/cli/restart_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Literal, TypedDict

import psutil

from app.cli.instance_control_pid import resolve_pid_file_path
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import open_text
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.tasks.task_cancellation_ops import cancel_task
from core.types.json import JSONValue
from core.types.json_value import filter_json_mapping_strict
from core.validation.integers import is_strict_int

__all__ = (
    "cancel_lifecycle_request_watch",
    "resolve_lifecycle_request_watch",
    "start_lifecycle_request_watch",
    "wait_for_lifecycle_request",
    "write_lifecycle_request",
)

OPERATION_LIFECYCLE_REQUEST_READ = "app.cli.lifecycle_request.read"
OPERATION_LIFECYCLE_REQUEST_REMOVE = "app.cli.lifecycle_request.remove"
OPERATION_LIFECYCLE_REQUEST_WRITE = "app.cli.lifecycle_request.write"
LIFECYCLE_REQUEST_FILENAME = "soai.lifecycle.json"
LIFECYCLE_REQUEST_POLL_INTERVAL_SECONDS: float = 0.25
PROCESS_CREATE_TIME_TOLERANCE_SECONDS: float = 0.001


@dataclass(frozen=True, slots=True)
class LifecycleRequest:
    action: Literal["restart", "stop"]
    pid: int
    create_time: float


class _LifecycleRequestFields(TypedDict):
    action: Literal["restart", "stop"]
    pid: int
    create_time: float


def write_lifecycle_request(
    base_dir: str,
    pid: int,
    action: Literal["restart", "stop"],
    logger: logging.Logger,
) -> str:
    if _coerce_lifecycle_action(action) is None:
        raise ValidationError("Lifecycle request action is invalid.")
    request_path = _resolve_lifecycle_request_path(base_dir, logger)
    try:
        process = psutil.Process(pid)
        payload: _LifecycleRequestFields = {
            "action": action,
            "pid": int(pid),
            "create_time": float(process.create_time()),
        }
        lifecycle_payload = filter_json_mapping_strict(
            payload,
            error_message="Lifecycle request must be JSON-compatible.",
        )
        os.makedirs(os.path.dirname(request_path), exist_ok=True)
        atomic_write_text_content(
            request_path,
            f"{serialize_json_compact_stable_strict(lifecycle_payload)}\n",
            encoding="utf-8",
            errors="strict",
            ensure_parent=False,
            fsync=True,
        )
    except psutil.NoSuchProcess:
        raise
    except psutil.Error as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to write {action} lifecycle request.",
            operation=OPERATION_LIFECYCLE_REQUEST_WRITE,
            details={"action": action, "pid": pid, "request_path": request_path},
            level="error",
        )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to write {action} lifecycle request.",
            operation=OPERATION_LIFECYCLE_REQUEST_WRITE,
            details={"action": action, "pid": pid, "request_path": request_path},
            level="error",
        )
        raise
    return request_path


async def wait_for_lifecycle_request(
    *,
    base_dir: str,
    stop_event: asyncio.Event,
    logger: logging.Logger,
) -> Literal["restart", "stop"] | None:
    while not stop_event.is_set():
        action = _consume_matching_lifecycle_request(base_dir, logger)
        if action is not None:
            stop_event.set()
            return action
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=LIFECYCLE_REQUEST_POLL_INTERVAL_SECONDS,
            )
        except TimeoutError:
            continue
    return None


def start_lifecycle_request_watch(
    *,
    base_dir: str,
    stop_event: asyncio.Event,
    logger: logging.Logger,
) -> asyncio.Task[Literal["restart", "stop"] | None]:
    return create_ephemeral_task(
        wait_for_lifecycle_request(
            base_dir=base_dir,
            stop_event=stop_event,
            logger=logger,
        ),
        name="windows-lifecycle-request-watch",
    )


async def resolve_lifecycle_request_watch(
    task: asyncio.Task[Literal["restart", "stop"] | None],
    *,
    stop_event: asyncio.Event,
) -> Literal["restart", "stop"] | None:
    if not task.done():
        await stop_event.wait()
    if not task.done():
        return await task
    return task.result()


async def cancel_lifecycle_request_watch(
    task: asyncio.Task[Literal["restart", "stop"] | None] | None,
    *,
    logger: logging.Logger,
) -> None:
    await cancel_task(task, logger=logger, label="windows-lifecycle-request-watch")


def _resolve_lifecycle_request_path(base_dir: str, logger: logging.Logger) -> str:
    pid_file_path = resolve_pid_file_path(base_dir, logger)
    return os.path.join(os.path.dirname(pid_file_path), LIFECYCLE_REQUEST_FILENAME)


def _coerce_lifecycle_action(value: JSONValue) -> Literal["restart", "stop"] | None:
    if value == "restart":
        return "restart"
    if value == "stop":
        return "stop"
    return None


def _consume_matching_lifecycle_request(
    base_dir: str,
    logger: logging.Logger,
) -> Literal["restart", "stop"] | None:
    request_path = _resolve_lifecycle_request_path(base_dir, logger)
    request = _read_lifecycle_request(request_path, logger)
    if request is None:
        return None
    current_pid = os.getpid()
    if request.pid != current_pid:
        _remove_lifecycle_request(request_path, logger)
        return None
    try:
        current_create_time = psutil.Process(current_pid).create_time()
    except psutil.Error as exception:
        log_exception(
            logger,
            exception,
            message="Failed to validate lifecycle request owner process.",
            operation=OPERATION_LIFECYCLE_REQUEST_READ,
            details={"request_path": request_path, "pid": current_pid},
            level="error",
        )
        _remove_lifecycle_request(request_path, logger)
        return None
    if abs(current_create_time - request.create_time) > PROCESS_CREATE_TIME_TOLERANCE_SECONDS:
        _remove_lifecycle_request(request_path, logger)
        return None
    _remove_lifecycle_request(request_path, logger)
    logger.info("Lifecycle request file accepted for PID %s: %s.", current_pid, request.action)
    return request.action


def _read_lifecycle_request(request_path: str, logger: logging.Logger) -> LifecycleRequest | None:
    try:
        with open_text(request_path, encoding="utf-8") as handle:
            payload = parse_json_dict(handle.read(), field="lifecycle request file")
    except FileNotFoundError:
        return None
    except ValidationError as exception:
        log_exception(
            logger,
            exception,
            message="Lifecycle request file is invalid.",
            operation=OPERATION_LIFECYCLE_REQUEST_READ,
            details={"request_path": request_path},
            level="warning",
        )
        _remove_lifecycle_request(request_path, logger)
        return None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to read lifecycle request file.",
            operation=OPERATION_LIFECYCLE_REQUEST_READ,
            details={"request_path": request_path},
            level="error",
        )
        return None
    pid_value = payload.get("pid")
    action = _coerce_lifecycle_action(payload.get("action"))
    create_time_value = payload.get("create_time")
    if action is None:
        _remove_lifecycle_request(request_path, logger)
        return None
    if not is_strict_int(pid_value):
        _remove_lifecycle_request(request_path, logger)
        return None
    if not isinstance(create_time_value, int | float) or isinstance(create_time_value, bool):
        _remove_lifecycle_request(request_path, logger)
        return None
    if pid_value <= 0:
        _remove_lifecycle_request(request_path, logger)
        return None
    return LifecycleRequest(
        action=action,
        pid=pid_value,
        create_time=float(create_time_value),
    )


def _remove_lifecycle_request(request_path: str, logger: logging.Logger) -> None:
    try:
        os.unlink(request_path)
    except FileNotFoundError:
        return
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to remove lifecycle request file.",
            operation=OPERATION_LIFECYCLE_REQUEST_REMOVE,
            details={"request_path": request_path},
            level="error",
        )
