"""SoAI - SoAIBench failed-start cleanup [backend/hardware/soaibench/start_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from hardware.soaibench.events import publish_soaibench_run_update
from hardware.soaibench.start_preworker_failure import (
    finish_preworker_failure_preserving,
)
from hardware.soaibench.types import SoAIBenchRunStatus

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.soaibench.dependencies import SoAIBenchServiceDependencies

__all__ = (
    "bind_run_id_or_finish_failed",
    "cleanup_cancelled_start",
    "cleanup_failed_start",
    "release_start_lease_preserving",
)

START_CLEANUP_OPERATION = "hardware.soaibench.start_cleanup"
RELEASE_LEASE_OPERATION = "hardware.soaibench.start_cleanup.release_lease"
PUBLISH_TERMINAL_OPERATION = "hardware.soaibench.start_cleanup.publish_terminal"


async def bind_run_id_or_finish_failed(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict,
    device_id: str,
    lease_id: str,
    run_id: str,
) -> None:
    try:
        bound = await deps.activity_registry.bind_run_id(
            device_id=device_id,
            lease_id=lease_id,
            run_id=run_id,
        )
        if not bound:
            raise ValidationError("SoAIBench activity lease binding failed.")
    except asyncio.CancelledError as exception:
        await _cleanup_bind_failure(deps, run, device_id, lease_id, exception)
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        await _cleanup_bind_failure(deps, run, device_id, lease_id, exception)
        raise


async def _cleanup_bind_failure(
    deps: SoAIBenchServiceDependencies,
    run: JSONDict,
    device_id: str,
    lease_id: str,
    primary_exception: BaseException,
) -> None:
    if isinstance(primary_exception, asyncio.CancelledError):
        await cleanup_cancelled_start(
            deps=deps,
            run=run,
            device_id=device_id,
            lease_id=lease_id,
            primary_exception=primary_exception,
        )
        return
    await cleanup_failed_start(
        deps=deps,
        run=run,
        device_id=device_id,
        lease_id=lease_id,
        reason="start_lease_bind_failed",
        operation=START_CLEANUP_OPERATION,
        log_message="SoAIBench activity lease binding failed.",
        primary_exception=primary_exception,
    )


async def cleanup_cancelled_start(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict | None,
    device_id: str,
    lease_id: str,
    primary_exception: BaseException,
) -> None:
    try:
        await _finish_start_terminal_preserving(
            deps=deps,
            run=run,
            status=SoAIBenchRunStatus.CANCELLED,
            reason=None,
            message="SoAIBench start was cancelled.",
            update_type="shutdown_cancelled",
            primary_exception=primary_exception,
        )
    finally:
        await release_start_lease_preserving(
            deps=deps,
            device_id=device_id,
            lease_id=lease_id,
            primary_exception=primary_exception,
        )


async def cleanup_failed_start(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict | None,
    device_id: str,
    lease_id: str,
    reason: str,
    operation: str,
    log_message: str,
    primary_exception: BaseException,
) -> None:
    coerced_exception = coerce_to_soai_error(
        primary_exception,
        operation=operation,
    )
    log_exception(
        deps.logger,
        coerced_exception,
        message=log_message,
        operation=operation,
    )
    try:
        await _finish_start_terminal_preserving(
            deps=deps,
            run=run,
            status=SoAIBenchRunStatus.FAILED,
            reason=reason,
            message="SoAIBench could not start.",
            update_type="terminal",
            primary_exception=primary_exception,
        )
    finally:
        await release_start_lease_preserving(
            deps=deps,
            device_id=device_id,
            lease_id=lease_id,
            primary_exception=primary_exception,
        )


async def _finish_start_terminal_preserving(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict | None,
    status: SoAIBenchRunStatus,
    reason: str | None,
    message: str,
    update_type: str,
    primary_exception: BaseException,
) -> None:
    if run is None:
        return
    terminal_run = await finish_preworker_failure_preserving(
        deps=deps,
        run=run,
        status=status,
        reason=reason,
        message=message,
        primary_exception=primary_exception,
    )
    if terminal_run is not None:
        await _publish_terminal_preserving(
            deps=deps,
            run=terminal_run,
            update_type=update_type,
            primary_exception=primary_exception,
        )


async def _publish_terminal_preserving(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict,
    update_type: str,
    primary_exception: BaseException,
) -> None:
    try:
        await uncancel_then_cleanup(
            publish_soaibench_run_update(
                event_bus=deps.event_bus,
                logger=deps.logger,
                run=run,
                update_type=update_type,
            ),
        )
    except asyncio.CancelledError as cleanup_exception:
        primary_exception.add_note(
            f"SoAIBench failed-start terminal publication was cancelled: {cleanup_exception}",
        )
    except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
        primary_exception.add_note(
            f"SoAIBench failed-start terminal publication failed: {cleanup_exception}",
        )
        coerced_exception = coerce_to_soai_error(
            cleanup_exception,
            operation=PUBLISH_TERMINAL_OPERATION,
        )
        log_exception(
            deps.logger,
            coerced_exception,
            message="SoAIBench failed-start terminal publication failed.",
            operation=PUBLISH_TERMINAL_OPERATION,
            details={"run_id": str(run["run_id"]), "update_type": update_type},
            level="warning",
        )


async def release_start_lease_preserving(
    *,
    deps: SoAIBenchServiceDependencies,
    device_id: str,
    lease_id: str,
    primary_exception: BaseException,
) -> None:
    try:
        await uncancel_then_cleanup(
            deps.activity_registry.release(device_id=device_id, lease_id=lease_id),
        )
    except asyncio.CancelledError as cleanup_exception:
        primary_exception.add_note(
            f"SoAIBench activity lease cleanup was cancelled: {cleanup_exception}",
        )
    except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
        primary_exception.add_note(f"SoAIBench activity lease cleanup failed: {cleanup_exception}")
        coerced_exception = coerce_to_soai_error(
            cleanup_exception,
            operation=RELEASE_LEASE_OPERATION,
        )
        log_exception(
            deps.logger,
            coerced_exception,
            message="SoAIBench activity lease cleanup failed.",
            operation=RELEASE_LEASE_OPERATION,
            level="warning",
        )
