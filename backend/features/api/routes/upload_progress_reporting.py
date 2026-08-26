"""SoAI - Shared staged upload progress reporting helpers [backend/features/api/routes/upload_progress_reporting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.progress.formatting import (
    calculate_eta,
    format_transfer_details,
    format_transfer_status_message,
)
from core.progress.percent import clamp_percent
from core.progress.speed import SpeedCalculator
from core.tasks.progress_reporting import report_progress_without_status_change
from core.tasks.status_transitions import update_progress

if TYPE_CHECKING:
    from core.logging.protocols import StandardLogger
    from core.tasks.protocols import TaskRegistryLifecycleView

__all__ = (
    "UploadProgressState",
    "compute_scaled_upload_percent",
    "emit_upload_progress_update",
)


@dataclass(slots=True)
class UploadProgressState:
    speed_calculator: SpeedCalculator
    last_reported_percent: int = -1
    last_reported_at: float = 0.0
    last_reported_bytes: int = -1


def compute_scaled_upload_percent(
    *,
    bytes_done: int,
    total_bytes: int | None,
    progress_start: int,
    progress_end: int,
) -> int:
    normalized_start = clamp_percent(progress_start)
    normalized_end = clamp_percent(progress_end)
    if normalized_end <= normalized_start:
        return normalized_end
    resolved_total = total_bytes if total_bytes is not None and total_bytes > 0 else None
    if resolved_total is None:
        if bytes_done > 0:
            return max(normalized_start, min(normalized_end, normalized_start + 1))
        return normalized_start
    span = normalized_end - normalized_start
    ratio = min(1.0, max(0.0, float(bytes_done) / float(resolved_total)))
    scaled = normalized_start + int(span * ratio)
    if ratio >= 1.0:
        return normalized_end
    return min(normalized_end, max(normalized_start, scaled))


async def emit_upload_progress_update(
    *,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    bytes_done: int,
    total_bytes: int | None,
    action: str,
    label: str,
    state: UploadProgressState,
    logger: StandardLogger,
    operation: str,
    progress_start: int = 0,
    progress_end: int = 99,
    min_interval_seconds: float = 0.25,
    keep_current_task_status: bool = False,
    recoverable_exceptions: tuple[type[Exception], ...] = RECOVERABLE_EXCEPTIONS,
    error_message: str = "Failed to emit upload progress update (non-critical).",
) -> None:
    now = time.monotonic()
    percent = compute_scaled_upload_percent(
        bytes_done=bytes_done,
        total_bytes=total_bytes,
        progress_start=progress_start,
        progress_end=progress_end,
    )
    should_report = percent != state.last_reported_percent or (
        now - state.last_reported_at >= min_interval_seconds
        and bytes_done != state.last_reported_bytes
    )
    if not should_report:
        return
    speed = state.speed_calculator.update(bytes_done)
    eta_seconds = (
        calculate_eta(speed, bytes_done, total_bytes)
        if total_bytes is not None and total_bytes > 0
        else 0.0
    )
    status_message = format_transfer_status_message(
        action,
        label,
        downloaded_size=bytes_done,
        total_size=total_bytes,
        speed=speed,
        eta_seconds=eta_seconds,
    )
    details = format_transfer_details(bytes_done, total_bytes, speed=speed, eta_seconds=eta_seconds)
    try:
        if keep_current_task_status:
            await report_progress_without_status_change(
                registry,
                task_id,
                percent,
                status_message=status_message,
                details=details,
                percent_override=percent,
            )
        else:
            await update_progress(
                registry,
                task_id,
                progress_current=percent,
                percent_override=percent,
                status_message=status_message,
                details=details,
            )
    except recoverable_exceptions as progress_error:
        log_handled_exception(
            logger,
            progress_error,
            message=error_message,
            operation=operation,
            details={"task_id": task_id},
            level="debug",
        )
    state.last_reported_percent = percent
    state.last_reported_at = now
    state.last_reported_bytes = bytes_done
