"""SoAI - Plugin process startup and model loading orchestration [backend/orchestrator/lifecycle/model_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.config.numeric_lenient import coerce_positive_timeout_seconds
from core.errors.exceptions import StateError
from core.metrics.keyspace_base import DIRECTOR_GAUGE_PENDING_LOADS
from core.tasks.task import Task
from orchestrator.lifecycle.model_loading_dependencies import (
    OrchestratorLifecycleModelLoadingDependencies,
)
from orchestrator.lifecycle.model_loading_execution import (
    execute_start_plugin_and_load_model,
)
from orchestrator.lifecycle.model_loading_result import ModelLoadingResult

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

    type ModelInfo = Mapping[str, JSONValue]

__all__ = ("OrchestratorLifecycleModelLoading",)


class OrchestratorLifecycleModelLoading:
    def __init__(self, deps: OrchestratorLifecycleModelLoadingDependencies) -> None:
        self._deps = deps
        self._health_check_config = deps.health_check_config
        self._pending_loads = 0
        self._pending_loads_lock = asyncio.Lock()

    def update_config(self, health_check_config: JSONDict) -> None:
        self._health_check_config = health_check_config

    async def _adjust_pending_loads(self, delta: int) -> None:
        async with self._pending_loads_lock:
            self._pending_loads = max(0, self._pending_loads + int(delta))
            self._deps.orchestrator.metrics.set_gauge(
                *DIRECTOR_GAUGE_PENDING_LOADS,
                value=self._pending_loads,
            )

    def _resolve_model_universal_id(self, model_info: ModelInfo) -> str:
        raw = model_info.get("universal_id")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        raise StateError("Model info missing required universal_id.")

    async def start_plugin_and_load_model(
        self,
        task: Task,
        plugin_name: str,
        model_info: ModelInfo,
    ) -> ModelLoadingResult:
        universal_id = self._resolve_model_universal_id(model_info)
        command_timeouts = self._health_check_config.get("COMMAND_TIMEOUTS_SEC")
        command_timeouts_map: dict[str, JSONValue] = (
            dict(command_timeouts) if isinstance(command_timeouts, dict) else {}
        )
        raw_timeout = command_timeouts_map.get("PLUGIN_LOAD_MODEL", 7200.0)
        load_timeout = coerce_positive_timeout_seconds(raw_timeout, default=7200.0)
        return await execute_start_plugin_and_load_model(
            self._deps,
            adjust_pending_loads=self._adjust_pending_loads,
            task=task,
            plugin_name=plugin_name,
            model_info=model_info,
            universal_id=universal_id,
            load_timeout=load_timeout,
        )
