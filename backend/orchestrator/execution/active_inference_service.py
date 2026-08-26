"""SoAI - Orchestrator active inference tracking and cancellation [backend/orchestrator/execution/active_inference_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.error_types import ErrorType
from core.plugins.name_validation import require_plugin_name
from core.validation.strings import coerce_optional_trimmed_str
from orchestrator.execution.internal_protocols import (
    ActiveInferenceRegistryProtocol,
    InflightCancellationManagerProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ActiveInferenceService",
    "ActiveInferenceServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class ActiveInferenceServiceDependencies:
    active_inferences: ActiveInferenceRegistryProtocol
    cancellations: InflightCancellationManagerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ActiveInferenceServiceDependencies",
            active_inferences=self.active_inferences,
            cancellations=self.cancellations,
        )


class ActiveInferenceService:
    def __init__(self, deps: ActiveInferenceServiceDependencies) -> None:
        self._deps = deps
        self.get_active_inference_tasks = deps.active_inferences.tasks
        self.get_active_inferences_snapshot = deps.active_inferences.snapshot

    async def fail_active_tasks(
        self,
        plugin_name: str,
        reason: str,
        *,
        allow_failover: bool,
        error_type: ErrorType,
    ) -> None:
        normalized_plugin_name = coerce_optional_trimmed_str(plugin_name)
        if normalized_plugin_name is None:
            return
        infos = await self._deps.active_inferences.list_for_plugin(normalized_plugin_name)
        for info in infos:
            self._deps.cancellations.fail_inflight(
                info,
                prefix="Force stop: ",
                reason=reason,
                allow_failover=allow_failover,
                error_type=error_type,
            )

    async def cancel_inflight_task(self, tracking_id: str, reason: str) -> None:
        if not tracking_id:
            return
        info = await self._deps.active_inferences.get(tracking_id)
        self._deps.cancellations.cancel_inflight(info, prefix="", reason=reason)

    async def fail_inflight_task(
        self,
        tracking_id: str,
        reason: str,
        *,
        allow_failover: bool,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
    ) -> None:
        if not tracking_id:
            return
        info = await self._deps.active_inferences.get(tracking_id)
        self._deps.cancellations.fail_inflight(
            info,
            prefix="",
            reason=reason,
            allow_failover=allow_failover,
            error_type=error_type,
        )

    async def get_active_task_count(self, plugin_name: str) -> int:
        normalized_plugin_name = require_plugin_name(plugin_name)
        return await self._deps.active_inferences.count_for_plugin(normalized_plugin_name)

    async def is_tracking_id_active(self, tracking_id: str) -> bool:
        if not tracking_id:
            return False
        return await self._deps.active_inferences.has_tracking_id(tracking_id)

    async def get_status_snapshot(self) -> JSONDict:
        active_inferences_summary = await self.get_active_inferences_snapshot()
        return {
            "active_inferences": active_inferences_summary,
            "active_inferences_count": len(active_inferences_summary),
        }
