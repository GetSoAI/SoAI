"""SoAI - SoAIBench start state persistence [backend/hardware/soaibench/start_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.hardware.soaibench_persistence import (
    SoAIBenchMutationOutcome,
    SoAIBenchMutationResult,
)
from core.serialization.json import serialize_json_compact_stable
from core.timing.epoch import epoch_ms
from core.types.json_value import coerce_json_dict_or_empty
from hardware.control_snapshots import find_gpu_entry
from hardware.soaibench.environment import system_evidence_from_snapshot
from hardware.soaibench.errors import SoAIBenchHeartbeatSuperseded
from hardware.soaibench.gpu_identity import identity_payload
from hardware.soaibench.telemetry import settings_snapshot_from_gpu
from hardware.soaibench.types import (
    SOAIBENCH_SCORE_VERSION,
    SoAIBenchBenchmarkMode,
    SoAIBenchProfile,
    SoAIBenchRunStatus,
)

if TYPE_CHECKING:
    from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
    from core.types.json import JSONDict
    from hardware.soaibench.dependencies import SoAIBenchServiceDependencies
    from hardware.soaibench.types import SoAIBenchGpuIdentity

__all__ = (
    "create_initial_run",
    "materialized_heartbeat_run",
    "persist_preflight_summary",
)


async def persist_preflight_summary(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    run: JSONDict,
    match: JSONDict,
) -> JSONDict:
    now_ms = epoch_ms()
    summary = coerce_json_dict_or_empty(run.get("summary"))
    summary.update(match)
    summary_json = serialize_json_compact_stable(summary)
    mutation = await database_hardware.update_soaibench_heartbeat(
        run_id=str(run["run_id"]),
        last_heartbeat_at_ms=now_ms,
        sample_count=0,
        summary_json=summary_json,
    )
    return materialized_heartbeat_run(mutation)


def materialized_heartbeat_run(
    mutation: SoAIBenchMutationResult,
) -> JSONDict:
    if mutation.outcome == SoAIBenchMutationOutcome.TERMINAL_SUPERSEDED:
        if mutation.run is None:
            raise StateError("SoAIBench superseded heartbeat has no durable run.")
        if (
            mutation.run.get("status") == SoAIBenchRunStatus.RUNNING.value
            and mutation.run.get("stop_requested_at_ms") is None
        ):
            raise StateError("SoAIBench heartbeat was superseded without a terminal decision.")
        raise SoAIBenchHeartbeatSuperseded(mutation.run)
    if mutation.outcome != SoAIBenchMutationOutcome.UPDATED or mutation.run is None:
        raise StateError("SoAIBench heartbeat persistence violated its result contract.")
    return mutation.run


async def create_initial_run(
    *,
    deps: SoAIBenchServiceDependencies,
    gpu_snapshot: JSONDict,
    identity: SoAIBenchGpuIdentity,
    run_id: str,
    device_id: str,
    profile: SoAIBenchProfile,
    benchmark_mode: SoAIBenchBenchmarkMode,
    user_id: int,
    created_by_tool: str,
    temperature_limit_celsius: float | None,
) -> JSONDict:
    gpu = find_gpu_entry(gpu_snapshot, device_id)
    settings_snapshot = settings_snapshot_from_gpu(gpu) if gpu is not None else {}
    summary = {
        "benchmark_mode": benchmark_mode.value,
        "temperature_limit_celsius": temperature_limit_celsius,
        **system_evidence_from_snapshot(gpu_snapshot),
    }
    run = {
        **identity_payload(identity),
        "run_id": run_id,
        "created_by_user_id": user_id,
        "profile": profile.value,
        "benchmark_mode": benchmark_mode.value,
        "status": SoAIBenchRunStatus.RUNNING.value,
        "score_version": SOAIBENCH_SCORE_VERSION,
        "started_at_ms": epoch_ms(),
        "update_seq": 0,
        "created_by_tool": created_by_tool,
        "publication_source_supported": True,
        "settings_snapshot_json": serialize_json_compact_stable(settings_snapshot),
        "summary_json": serialize_json_compact_stable(summary),
    }
    mutation = await deps.database_hardware.create_soaibench_run(run)
    if mutation.run is None:
        raise StateError("SoAIBench initial persistence did not return a durable run.")
    return mutation.run
