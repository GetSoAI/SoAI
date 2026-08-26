"""SoAI - SoAIBench native task identity resolution [backend/hardware/soaibench/task_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from hardware.soaibench.runtime import task_id_for_run

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict

__all__ = (
    "attach_existing_task_id",
    "attach_existing_task_ids",
)


async def attach_existing_task_id(
    task_registry: TaskRegistryProtocol,
    run: JSONDict,
) -> JSONDict:
    run_id_value = run.get("run_id")
    if not isinstance(run_id_value, str) or not run_id_value:
        run["task_id"] = None
        return run
    task_id = task_id_for_run(run_id_value)
    task = await task_registry.get(task_id, force_refresh=True)
    run["task_id"] = task_id if task is not None else None
    return run


async def attach_existing_task_ids(
    task_registry: TaskRegistryProtocol,
    runs: list[JSONDict],
) -> list[JSONDict]:
    for run in runs:
        await attach_existing_task_id(task_registry, run)
    return runs
