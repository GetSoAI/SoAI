"""SoAI - Backup restore runtime quiescence [backend/app/backup/restore_runtime_quiescence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.lifecycle.budgets import resolve_lifecycle_shutdown_budgets
from app.lifecycle.runner import LifecycleRunner
from app.lifecycle.shutdown_infrastructure_plan import (
    build_pre_shutdown_quiesce_entries,
)
from app.lifecycle.shutdown_service_plan import (
    build_restore_service_shutdown_entries,
)
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from app.types_application import ApplicationContext

__all__ = (
    "RestoreRuntimeQuiescence",
    "RestoreRuntimeQuiescenceDependencies",
)


@dataclass(frozen=True, slots=True)
class RestoreRuntimeQuiescenceDependencies:
    application_context: ApplicationContext
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="RestoreRuntimeQuiescenceDependencies",
            application_context=self.application_context,
            logger=self.logger,
        )


class RestoreRuntimeQuiescence:
    def __init__(self, deps: RestoreRuntimeQuiescenceDependencies) -> None:
        self._application_context = deps.application_context
        self._logger = deps.logger

    async def shutdown(self) -> None:
        budgets = resolve_lifecycle_shutdown_budgets(
            self._application_context.services.configuration.config,
        )
        entries = (
            *build_pre_shutdown_quiesce_entries(
                self._application_context,
                component_timeout_sec=budgets.component_timeout_sec,
            ),
            *build_restore_service_shutdown_entries(
                self._application_context,
                component_timeout_sec=budgets.component_timeout_sec,
                orchestrator_timeout_sec=budgets.orchestrator_timeout_sec,
                mcp_timeout_sec=budgets.mcp_timeout_sec,
            ),
        )
        failures = await LifecycleRunner(logger=self._logger).run_entries_continue(entries)
        if failures:
            raise StateError(
                "Runtime services did not quiesce safely for database restore.",
                details={
                    "failed_components": [failure.component_name for failure in failures],
                },
            )
