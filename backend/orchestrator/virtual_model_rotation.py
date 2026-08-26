"""SoAI - Identity-based virtual model rotation [backend/orchestrator/virtual_model_rotation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from core.concurrency.lock_registry import TTLAsyncLockRegistry, TTLAsyncLockRegistryDependencies
from core.di.validation import require_dependencies
from core.orchestrator.routing_config import ConstituentModelConfig
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig

__all__ = ("VirtualModelRotation", "VirtualModelRotationDependencies")


@dataclass(frozen=True, slots=True)
class VirtualModelRotationDependencies:
    config: OrchestratorRuntimeConfig

    def __post_init__(self) -> None:
        require_dependencies(owner="VirtualModelRotationDependencies", config=self.config)


class VirtualModelRotation:
    def __init__(self, deps: VirtualModelRotationDependencies) -> None:
        self._config = deps.config
        self._last_selected_universal_ids: dict[str, str] = {}
        self._rotation_locks: TTLAsyncLockRegistry[str] = TTLAsyncLockRegistry(
            TTLAsyncLockRegistryDependencies(
                ttl_seconds=3600.0,
                max_size=2000,
                cleanup_interval_seconds=300.0,
            ),
        )

    def update_config(self, config: OrchestratorRuntimeConfig) -> None:
        self._config = config

    async def select_next_candidate(
        self,
        virtual_model_name: str,
        models: Sequence[ConstituentModelConfig],
    ) -> list[ConstituentModelConfig]:
        ordered_models = list(models)
        if not (
            self._config.fair_task_rotation_enabled
            and virtual_model_name
            and len(ordered_models) > 1
        ):
            return ordered_models
        async with self._rotation_locks.lock(virtual_model_name):
            previous_id = self._last_selected_universal_ids.get(virtual_model_name)
            selected_index = 0
            if previous_id is not None:
                previous_index = next(
                    (
                        index
                        for index, model in enumerate(ordered_models)
                        if model.universal_id == previous_id
                    ),
                    None,
                )
                if previous_index is not None:
                    selected_index = (previous_index + 1) % len(ordered_models)
            selected = ordered_models[selected_index]
            self._last_selected_universal_ids[virtual_model_name] = selected.universal_id
            if selected_index == 0:
                return ordered_models
            return [
                selected,
                *ordered_models[:selected_index],
                *ordered_models[selected_index + 1 :],
            ]

    async def prune(self, active_names: set[str]) -> None:
        stale_names = [
            name for name in self._last_selected_universal_ids if name not in active_names
        ]
        for name in stale_names:
            async with self._rotation_locks.lock(name):
                self._last_selected_universal_ids.pop(name, None)
            await self._rotation_locks.remove(name)
