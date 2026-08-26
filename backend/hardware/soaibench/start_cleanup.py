"""SoAI - SoAIBench failed-start cleanup [backend/hardware/soaibench/start_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.validation.numberish import require_int_from_numberish
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.events import publish_soaibench_run_update
from hardware.soaibench.preflight import finish_preflight_unsupported
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
    "finish_preflight_unsupported_and_release",
    "release_start_lease_preserving",
)

PREFLIGHT_UNSUPPORTED_OPERATION = "hardware.soaibench.start_cleanup.preflight_unsupported"
START_CLEANUP_OPERATION = "hardware.soaibench.start_cleanup"
RELEASE_LEASE_OPERATION = "hardware.soaibench.start_cleanup.release_lease"


async def finish_preflight_unsupported_and_release(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict,
    exception: SoAIBenchUnsupported,
    device_id: str,
    lease_id: str,
) -> JSONDict:
    try:
        terminal = await finish_preflight_unsupported(
            database_hardware=deps.database_hardware,
            run=run,
            exception=exception,
        )
    except asyncio.CancelledError as finish_exception:
        await release_start_lease_preserving(
            deps=deps,
            device_id=device_id,
            lease_id=lease_id,
            primary_exception=finish_exception,
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as finish_exception:
        coerced_exception = coerce_to_soai_error(
            finish_exception,
            operation=PREFLIGHT_UNSUPPORTED_OPERATION,
        )
        log_exception(
            deps.logger,
            coerced_exception,
            message="SoAIBench unsupported preflight cleanup failed.",
            operation=PREFLIGHT_UNSUPPORTED_OPERATION,
            level="warning",
        )
        await release_start_lease_preserving(
            deps=deps,
            device_id=device_id,
            lease_id=lease_id,
            primary_exception=finish_exception,
        )
        raise
    await deps.activity_registry.release(device_id=device_id, lease_id=lease_id)
    return terminal


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
        await _cleanup_cancelled_lease_binding(
            deps=deps,
            run=run,
            device_id=device_id,
            lease_id=lease_id,
            run_id=run_id,
            primary_exception=exception,
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        await _cleanup_failed_lease_binding(
            deps=deps,
            run=run,
            device_id=device_id,
            lease_id=lease_id,
            run_id=run_id,
            primary_exception=exception,
        )
        raise


async def _cleanup_cancelled_lease_binding(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict,
    device_id: str,
    lease_id: str,
    run_id: str,
    primary_exception: BaseException,
) -> None:
    await cleanup_cancelled_start(
        deps=deps,
        run=run,
        user_id=require_int_from_numberish(
            run["created_by_user_id"],
            field="created_by_user_id",
        ),
        device_id=device_id,
        lease_id=lease_id,
        run_id=run_id,
        primary_exception=primary_exception,
    )


async def _cleanup_failed_lease_binding(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict,
    device_id: str,
    lease_id: str,
    run_id: str,
    primary_exception: BaseException,
) -> None:
    await cleanup_failed_start(
        deps=deps,
        run=run,
        user_id=require_int_from_numberish(
            run["created_by_user_id"],
            field="created_by_user_id",
        ),
        device_id=device_id,
        lease_id=lease_id,
        run_id=run_id,
        reason="start_lease_bind_failed",
        operation=START_CLEANUP_OPERATION,
        log_message="SoAIBench activity lease binding failed.",
        primary_exception=primary_exception,
    )


async def cleanup_cancelled_start(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict | None,
    user_id: int,
    device_id: str,
    lease_id: str,
    run_id: str,
    primary_exception: BaseException,
) -> None:
    if run is not None:
        await finish_preworker_failure_preserving(
            deps=deps,
            run=run,
            status=SoAIBenchRunStatus.CANCELLED,
            reason=None,
            message="SoAIBench start was cancelled.",
            primary_exception=primary_exception,
        )
        await publish_soaibench_run_update(
            database_hardware=deps.database_hardware,
            event_bus=deps.event_bus,
            logger=deps.logger,
            user_id=user_id,
            run_id=run_id,
            update_type="shutdown_cancelled",
        )
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
    user_id: int,
    device_id: str,
    lease_id: str,
    run_id: str,
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
    if run is not None:
        await finish_preworker_failure_preserving(
            deps=deps,
            run=run,
            status=SoAIBenchRunStatus.FAILED,
            reason=reason,
            message=str(primary_exception),
            primary_exception=primary_exception,
        )
        await publish_soaibench_run_update(
            database_hardware=deps.database_hardware,
            event_bus=deps.event_bus,
            logger=deps.logger,
            user_id=user_id,
            run_id=run_id,
            update_type="terminal",
        )
    await release_start_lease_preserving(
        deps=deps,
        device_id=device_id,
        lease_id=lease_id,
        primary_exception=primary_exception,
    )


async def release_start_lease_preserving(
    *,
    deps: SoAIBenchServiceDependencies,
    device_id: str,
    lease_id: str,
    primary_exception: BaseException,
) -> None:
    try:
        await deps.activity_registry.release(device_id=device_id, lease_id=lease_id)
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
