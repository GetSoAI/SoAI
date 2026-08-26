"""SoAI - SoAIBench run start flow [backend/hardware/soaibench/start_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallActivity
from hardware.activity_leases import lease_conflict_payload
from hardware.soaibench.active_runs import ActiveSoAIBenchRuns
from hardware.soaibench.deferred_tool_activity import (
    mark_soaibench_deferred_tool_activity_accepted,
)
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.events import publish_soaibench_run_update
from hardware.soaibench.gpu_identity import identity_from_payload
from hardware.soaibench.preflight import run_preflight
from hardware.soaibench.registration import register_soaibench_worker
from hardware.soaibench.registration_context import SoAIBenchRegistrationContext
from hardware.soaibench.responses import run_response
from hardware.soaibench.runtime import (
    CERTIFIED_DEFAULT_TEMPERATURE_LIMIT_CELSIUS,
    parse_benchmark_mode,
    parse_profile,
    parse_temperature_limit_celsius,
    task_id_for_run,
)
from hardware.soaibench.start_cleanup import (
    bind_run_id_or_finish_failed,
    cleanup_cancelled_start,
    cleanup_failed_start,
    finish_preflight_unsupported_and_release,
    release_start_lease_preserving,
)
from hardware.soaibench.start_state import create_initial_run, persist_preflight_summary
from hardware.soaibench.types import (
    SoAIBenchBenchmarkMode,
    SoAIBenchGpuIdentity,
    SoAIBenchProfile,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.types.json import JSONDict
    from hardware.soaibench.dependencies import SoAIBenchServiceDependencies

__all__ = ("start_soaibench_run",)

START_FLOW_OPERATION = "hardware.soaibench.start_flow"


async def start_soaibench_run(
    *,
    deps: SoAIBenchServiceDependencies,
    active_runs: ActiveSoAIBenchRuns,
    resolve_identity: Callable[[str], Awaitable[SoAIBenchGpuIdentity]],
    device_id: str,
    profile: str,
    benchmark_mode: str,
    created_by_user_id: int,
    created_by_tool: str,
    temperature_limit_celsius: float | None,
    deferred_tool_activity: DeferredToolCallActivity | None,
) -> JSONDict:
    parsed_profile = parse_profile(profile)
    parsed_mode = parse_benchmark_mode(benchmark_mode)
    effective_temperature_limit = _effective_temperature_limit(
        parsed_mode,
        parse_temperature_limit_celsius(temperature_limit_celsius),
    )
    acquire = await deps.activity_registry.acquire(
        device_id=device_id,
        activity_type=f"soaibench_{parsed_profile.value}",
        owner_id=str(created_by_user_id),
        conflict_reason=_conflict_reason(parsed_profile),
    )
    if acquire.conflict is not None:
        return lease_conflict_payload(acquire.conflict)
    if acquire.lease is None:
        raise SoAIBenchUnsupported(
            reason="opencl_runtime_error",
            message="SoAIBench activity lease acquisition failed.",
        )
    run_id = uuid.uuid4().hex
    lease_id = acquire.lease.lease_id
    run: JSONDict | None = None
    task_id: str | None = None
    try:
        run = await create_initial_run(
            deps=deps,
            resolve_identity=resolve_identity,
            run_id=run_id,
            device_id=device_id,
            profile=parsed_profile,
            benchmark_mode=parsed_mode,
            user_id=created_by_user_id,
            created_by_tool=created_by_tool,
            temperature_limit_celsius=effective_temperature_limit,
        )
        await publish_soaibench_run_update(
            database_hardware=deps.database_hardware,
            event_bus=deps.event_bus,
            logger=deps.logger,
            user_id=created_by_user_id,
            run_id=run_id,
            update_type="created",
        )
        async with deps.opencl_pool.lease() as opencl_pool:
            match = await run_preflight(
                opencl_pool=opencl_pool,
                identity=identity_from_payload(run),
            )
    except SoAIBenchUnsupported as exception:
        if run is None:
            await release_start_lease_preserving(
                deps=deps,
                device_id=device_id,
                lease_id=lease_id,
                primary_exception=exception,
            )
            raise
        terminal = await finish_preflight_unsupported_and_release(
            deps=deps,
            run=run,
            exception=exception,
            device_id=device_id,
            lease_id=lease_id,
        )
        terminal["task_id"] = None
        await publish_soaibench_run_update(
            database_hardware=deps.database_hardware,
            event_bus=deps.event_bus,
            logger=deps.logger,
            user_id=created_by_user_id,
            run_id=run_id,
            update_type="terminal",
        )
        return run_response(terminal, accepted=False)
    except asyncio.CancelledError as exception:
        await cleanup_cancelled_start(
            deps=deps,
            run=run,
            user_id=created_by_user_id,
            device_id=device_id,
            lease_id=lease_id,
            run_id=run_id,
            primary_exception=exception,
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        await cleanup_failed_start(
            deps=deps,
            run=run,
            user_id=created_by_user_id,
            device_id=device_id,
            lease_id=lease_id,
            run_id=run_id,
            reason="start_preflight_failed",
            operation=START_FLOW_OPERATION,
            log_message="SoAIBench start failed before worker registration.",
            primary_exception=exception,
        )
        raise
    await persist_preflight_summary(
        deps=deps,
        run=run,
        match=match,
    )
    task_id = task_id_for_run(run_id)
    run["task_id"] = task_id
    accepted_response = run_response(run, accepted=True)
    await bind_run_id_or_finish_failed(
        deps=deps,
        run=run,
        device_id=device_id,
        lease_id=lease_id,
        run_id=run_id,
    )
    deferred_response = await _mark_deferred_accepted_or_cleanup(
        deps=deps,
        deferred_tool_activity=deferred_tool_activity,
        accepted_response=accepted_response,
        task_id=task_id,
        run=run,
        device_id=device_id,
        lease_id=lease_id,
        run_id=run_id,
        user_id=created_by_user_id,
    )
    stop_event = asyncio.Event()
    start_execution_event = asyncio.Event()
    await register_soaibench_worker(
        context=SoAIBenchRegistrationContext(
            deps=deps,
            active_runs=active_runs,
            run=run,
            run_id=run_id,
            task_id=task_id,
            device_id=device_id,
            lease_id=lease_id,
            user_id=created_by_user_id,
            stop_event=stop_event,
            start_execution_event=start_execution_event,
            deferred_tool_activity=deferred_tool_activity,
        ),
    )
    try:
        await publish_soaibench_run_update(
            database_hardware=deps.database_hardware,
            event_bus=deps.event_bus,
            logger=deps.logger,
            user_id=created_by_user_id,
            run_id=run_id,
            update_type="preflight",
            task_id=task_id,
        )
    finally:
        start_execution_event.set()
    return deferred_response if deferred_response is not None else accepted_response


async def _mark_deferred_accepted_or_cleanup(
    *,
    deps: SoAIBenchServiceDependencies,
    deferred_tool_activity: DeferredToolCallActivity | None,
    accepted_response: JSONDict,
    task_id: str,
    run: JSONDict,
    device_id: str,
    lease_id: str,
    run_id: str,
    user_id: int,
) -> JSONDict | None:
    if deferred_tool_activity is None:
        return None
    try:
        return await mark_soaibench_deferred_tool_activity_accepted(
            deferred_tool_activity,
            owner_task_id=task_id,
            accepted_result=accepted_response,
        )
    except asyncio.CancelledError as exception:
        await cleanup_cancelled_start(
            deps=deps,
            run=run,
            user_id=user_id,
            device_id=device_id,
            lease_id=lease_id,
            run_id=run_id,
            primary_exception=exception,
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        await cleanup_failed_start(
            deps=deps,
            run=run,
            user_id=user_id,
            device_id=device_id,
            lease_id=lease_id,
            run_id=run_id,
            reason="deferred_tool_activity_acceptance_failed",
            operation=START_FLOW_OPERATION,
            log_message="SoAIBench deferred tool activity acceptance failed.",
            primary_exception=exception,
        )
        raise


def _conflict_reason(profile: SoAIBenchProfile) -> str:
    if profile == SoAIBenchProfile.STANDARD:
        return "duplicate_standard_benchmark"
    return "duplicate_stress_benchmark"


def _effective_temperature_limit(
    benchmark_mode: SoAIBenchBenchmarkMode,
    temperature_limit_celsius: float | None,
) -> float | None:
    if temperature_limit_celsius is not None:
        return temperature_limit_celsius
    if benchmark_mode == SoAIBenchBenchmarkMode.CERTIFIED:
        return CERTIFIED_DEFAULT_TEMPERATURE_LIMIT_CELSIUS
    return None
