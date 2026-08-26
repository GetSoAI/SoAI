"""SoAI - Task terminal progress logging helpers [backend/tasks/registry/terminal_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import dataclasses
import time

from core.errors.exception_logging import log_handled_exception
from core.logging.trace import get_logger
from core.progress.progress_bar import format_progress_bar
from core.tasks.enums import TaskStatus
from core.tasks.task import Task

__all__ = (
    "TerminalProgressState",
    "prune_stale_terminal_progress",
    "try_log_terminal_progress",
)

LOGGER_NAME = "SoAI.tasks.registry.terminal_progress"
OPERATION = "tasks.registry.terminal_progress.log"


@dataclasses.dataclass(slots=True)
class TerminalProgressState:
    last_percent: int | None = None
    last_message: str = ""
    last_logged_at: float = 0.0
    zero_percent_logged: bool = False


PROGRESS_BAR_LOG_THROTTLE_SECONDS: float = 1.0


def try_log_terminal_progress(
    task: Task,
    *,
    old_status: TaskStatus,
    states: dict[str, TerminalProgressState],
) -> None:
    logger_progress = get_logger(LOGGER_NAME)
    try:
        now = time.monotonic()
        task_id = task.task_id
        state = states.get(task_id)
        if state is None:
            state = TerminalProgressState()
            states[task_id] = state
        message = (task.status_message or "").strip()
        percent_value = task.progress_percent()
        percent = int(percent_value) if isinstance(percent_value, int | float) else None
        if percent is not None and 0 <= percent <= 100:
            last_percent = state.last_percent
            if last_percent is not None and percent < last_percent:
                percent = last_percent
            if percent == 0 and state.zero_percent_logged:
                return
            if (
                last_percent is not None
                and percent == last_percent
                and (now - state.last_logged_at < PROGRESS_BAR_LOG_THROTTLE_SECONDS)
            ):
                return
            state.last_percent = percent
            state.last_message = message
            state.last_logged_at = now
            if percent == 0:
                state.zero_percent_logged = True
            prefix = f"[Task/{task.task_type}] "
            suffix = f" ({task.task_id})"
            logger_progress.info(
                "%s%s %s%s",
                prefix,
                message or task.status.value,
                format_progress_bar(percent),
                suffix,
            )
            if task.status.is_terminal():
                states.pop(task_id, None)
            return
        if not message:
            if old_status != task.status and now - state.last_logged_at >= 1.0:
                state.last_logged_at = now
                logger_progress.info(
                    "[Task/%s] %s (%s)",
                    task.task_type,
                    task.status.value,
                    task.task_id,
                )
                if task.status.is_terminal():
                    states.pop(task_id, None)
            return
        if message == state.last_message:
            return
        if now - state.last_logged_at < 2.0:
            return
        state.last_message = message
        state.last_logged_at = now
        logger_progress.info("[Task/%s] %s (%s)", task.task_type, message, task.task_id)
        if task.status.is_terminal():
            states.pop(task_id, None)
    except (RuntimeError, TypeError, ValueError, AttributeError) as exception:
        log_handled_exception(
            logger_progress,
            exception,
            message="Failed to log terminal progress.",
            operation=OPERATION,
            level="debug",
        )


def prune_stale_terminal_progress(
    states: dict[str, TerminalProgressState],
    *,
    known_task_ids: set[str],
) -> int:
    stale_ids = [task_id for task_id in states if task_id not in known_task_ids]
    for task_id in stale_ids:
        del states[task_id]
    return len(stale_ids)
