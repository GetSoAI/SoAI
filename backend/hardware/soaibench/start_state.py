"""SoAI - SoAIBench start state persistence [backend/hardware/soaibench/start_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_optional_json_dict
from core.timing.epoch import epoch_ms
from core.validation.integers import coerce_non_negative_exact_int_or_zero
from hardware.control_snapshots import find_gpu_entry
from hardware.soaibench.gpu_identity import identity_payload
from hardware.soaibench.telemetry import settings_snapshot_from_gpu
from hardware.soaibench.types import (
    SoAIBenchBenchmarkMode,
    SoAIBenchGpuIdentity,
    SoAIBenchProfile,
    SoAIBenchRunStatus,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.types.json import JSONDict
    from hardware.soaibench.dependencies import SoAIBenchServiceDependencies

__all__ = ("create_initial_run", "persist_preflight_summary")


async def persist_preflight_summary(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict,
    match: JSONDict,
) -> None:
    now_ms = epoch_ms()
    summary_json_value = run.get("summary_json")
    summary = parse_optional_json_dict(
        summary_json_value if isinstance(summary_json_value, str) else None,
        field="summary_json",
    )
    if summary is None:
        summary = {}
    summary.update(match)
    summary_json = serialize_json_compact_stable(summary)
    await deps.database_hardware.update_soaibench_heartbeat(
        run_id=str(run["run_id"]),
        last_heartbeat_at_ms=now_ms,
        sample_count=0,
        summary_json=summary_json,
    )
    run["summary_json"] = summary_json
    run["last_heartbeat_at_ms"] = now_ms
    run["update_seq"] = coerce_non_negative_exact_int_or_zero(run.get("update_seq")) + 1
    run["match_basis"] = match.get("match_basis")


async def create_initial_run(
    *,
    deps: SoAIBenchServiceDependencies,
    resolve_identity: Callable[[str], Awaitable[SoAIBenchGpuIdentity]],
    run_id: str,
    device_id: str,
    profile: SoAIBenchProfile,
    benchmark_mode: SoAIBenchBenchmarkMode,
    user_id: int,
    created_by_tool: str,
    temperature_limit_celsius: float | None,
) -> JSONDict:
    identity = await resolve_identity(device_id)
    settings_snapshot = await _initial_settings_snapshot(deps, device_id)
    summary = {
        "benchmark_mode": benchmark_mode.value,
        "temperature_limit_celsius": temperature_limit_celsius,
    }
    run = {
        **identity_payload(identity),
        "run_id": run_id,
        "created_by_user_id": user_id,
        "profile": profile.value,
        "benchmark_mode": benchmark_mode.value,
        "status": SoAIBenchRunStatus.RUNNING.value,
        "started_at_ms": epoch_ms(),
        "update_seq": 0,
        "created_by_tool": created_by_tool,
        "settings_snapshot_json": serialize_json_compact_stable(settings_snapshot),
        "summary_json": serialize_json_compact_stable(summary),
    }
    await deps.database_hardware.create_soaibench_run(run)
    return run


async def _initial_settings_snapshot(
    deps: SoAIBenchServiceDependencies,
    device_id: str,
) -> JSONDict:
    snapshot = await deps.hardware_manager.get_system_info(["gpu"], cache=False)
    gpu = find_gpu_entry(snapshot, device_id)
    if gpu is None:
        return {}
    return settings_snapshot_from_gpu(gpu)
