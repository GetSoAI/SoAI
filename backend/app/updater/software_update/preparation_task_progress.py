"""SoAI - Durable task projection of updater preparation [backend/app/updater/software_update/preparation_task_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import Literal

from app.updater.software_update.preparation_status import UpdatePreparationStatus
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.serialization.json import serialize_json_compact_stable
from core.tasks.enums import TaskStatus
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.status_transitions import update_status
from core.timing.constants import MODERATE_DELAY_SEC

__all__ = ("observe_preparation_task_progress",)

OPERATION = "software_update.preparation_task_progress"
PROJECTION_ATTEMPTS = 3


async def mark_preparation_task_progress_unavailable(
    registry: TaskRegistryProtocol,
    task_id: str,
    status: UpdatePreparationStatus,
    logger: LoggerProtocol,
) -> bool:
    result = await _retry_projection(
        registry,
        task_id,
        status,
        status_message="Software update preparation progress is temporarily unavailable.",
        progress_details=serialize_json_compact_stable(
            {
                "active": True,
                "task_id": task_id,
                "phase": "unavailable",
                "progress_observation": "unavailable",
            }
        ),
        emit_progress_event=True,
    )
    if result == "degraded":
        logger.warning(
            "Software update task progress could not be marked unavailable after bounded retries.",
            extra={"task_id": task_id},
        )
    return result == "updated"


async def _retry_projection(
    registry: TaskRegistryProtocol,
    task_id: str,
    status: UpdatePreparationStatus,
    *,
    status_message: str,
    progress_details: str,
    emit_progress_event: bool,
) -> Literal["updated", "terminal", "superseded", "degraded"]:
    for attempt in range(PROJECTION_ATTEMPTS):
        if status.active_task_id != task_id:
            return "superseded"
        try:
            task = await update_status(
                registry,
                task_id,
                TaskStatus.WORKING,
                status_message=status_message,
                progress_details=progress_details,
                emit_progress_event=emit_progress_event,
            )
            if status.active_task_id != task_id:
                return "superseded"
            if task is not None:
                return "updated"
            refreshed = await registry.get(task_id, force_refresh=True)
            if status.active_task_id != task_id:
                return "superseded"
            if refreshed is None or refreshed.status.is_terminal():
                return "terminal"
        except HANDLED_RUNTIME_EXCEPTIONS:
            if attempt == PROJECTION_ATTEMPTS - 1:
                return "degraded"
        if attempt < PROJECTION_ATTEMPTS - 1:
            await asyncio.sleep(MODERATE_DELAY_SEC)
    return "degraded"


async def observe_preparation_task_progress(
    status: UpdatePreparationStatus,
    registry: TaskRegistryProtocol,
    task_id: str,
    logger: LoggerProtocol,
) -> Literal["terminal", "superseded", "degraded"]:
    try:
        previous: str | None = None
        while status.active_task_id == task_id:
            progress = await status.get_status()
            if status.active_task_id != task_id or progress.get("task_id") != task_id:
                return "superseded"
            details = serialize_json_compact_stable(progress)
            if details != previous:
                projection = await _retry_projection(
                    registry,
                    task_id,
                    status,
                    status_message="Software update preparation is in progress.",
                    progress_details=details,
                    emit_progress_event=True,
                )
                if projection == "terminal":
                    return "terminal"
                if projection == "superseded":
                    return "superseded"
                if projection == "degraded":
                    await mark_preparation_task_progress_unavailable(
                        registry,
                        task_id,
                        status,
                        logger,
                    )
                    return "degraded"
                previous = details
            await asyncio.sleep(MODERATE_DELAY_SEC)
        return "superseded"
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Software update task progress is degraded.",
            operation=OPERATION,
            details={"task_id": task_id},
        )
        return "degraded"
