"""SoAI - SoAIBench active worker tracking [backend/hardware/soaibench/active_runs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.errors.exceptions import ValidationError

__all__ = (
    "ActiveSoAIBenchRun",
    "ActiveSoAIBenchRuns",
)


@dataclass(frozen=True, slots=True)
class ActiveSoAIBenchRun:
    run_id: str
    task_id: str
    device_id: str
    lease_id: str
    stop_event: asyncio.Event
    worker: asyncio.Task[None] | None = None


class ActiveSoAIBenchRuns:
    def __init__(self) -> None:
        self._runs_by_id: dict[str, ActiveSoAIBenchRun] = {}
        self._run_ids_by_device: dict[str, str] = {}

    def bind_tracked_worker(self, run: ActiveSoAIBenchRun) -> None:
        if not run.run_id or not run.device_id or not run.lease_id:
            raise ValidationError("run_id, device_id, and lease_id are required.")
        if run.worker is None:
            raise ValidationError("worker is required.")
        active_device_run_id = self._run_ids_by_device.get(run.device_id)
        if active_device_run_id is not None and active_device_run_id != run.run_id:
            raise ValidationError("device already has an active SoAIBench run.")
        existing = self._runs_by_id.get(run.run_id)
        if existing is not None and existing.device_id != run.device_id:
            existing_device_run_id = self._run_ids_by_device.get(existing.device_id)
            if existing_device_run_id == run.run_id:
                self._run_ids_by_device.pop(existing.device_id, None)
        self._runs_by_id[run.run_id] = run
        self._run_ids_by_device[run.device_id] = run.run_id

    def get(self, run_id: str) -> ActiveSoAIBenchRun | None:
        return self._runs_by_id.get(run_id)

    def unbind(self, *, run_id: str, lease_id: str) -> bool:
        active = self._runs_by_id.get(run_id)
        if active is None or active.lease_id != lease_id:
            return False
        self._runs_by_id.pop(run_id, None)
        current_device_run_id = self._run_ids_by_device.get(active.device_id)
        if current_device_run_id == run_id:
            self._run_ids_by_device.pop(active.device_id, None)
        return True

    def all_runs(self) -> list[ActiveSoAIBenchRun]:
        return list(self._runs_by_id.values())

    def clear(self) -> None:
        self._runs_by_id.clear()
        self._run_ids_by_device.clear()
