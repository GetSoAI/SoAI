"""SoAI - Application update service [backend/app/application_update_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from app.application_update_dependencies import ApplicationUpdateServiceDependencies
from app.updater.software_update.diagnostics_store import SoftwareUpdateDiagnosticsStore
from app.updater.software_update.notice_store import SoftwareUpdateNoticeStore
from app.updater.software_update.preparation_status import UpdatePreparationStatus
from app.updater.software_update.preparation_transaction import (
    UpdatePreparationTransaction,
    UpdatePreparationTransactionDependencies,
)
from core.app.update_result import ApplicationUpdateResult
from core.types.json import JSONDict

__all__ = ("ApplicationUpdateService",)


class ApplicationUpdateService:
    def __init__(self, deps: ApplicationUpdateServiceDependencies) -> None:
        self._deps = deps
        self._update_lock = asyncio.Lock()
        self._preparation_status = UpdatePreparationStatus(deps.paths.base_dir, deps.logging.logger)
        self._transaction = UpdatePreparationTransaction(
            UpdatePreparationTransactionDependencies(deps, self._preparation_status)
        )
        self._notice_store = SoftwareUpdateNoticeStore(deps.paths.base_dir, deps.logging.logger)
        self._diagnostics_store = SoftwareUpdateDiagnosticsStore(
            deps.paths.base_dir, deps.logging.logger
        )

    async def get_preparation_status(self) -> JSONDict:
        return await self._preparation_status.get_status()

    async def get_update_notice(self, user_id: int) -> JSONDict | None:
        return await self._notice_store.get_pending_notice(user_id)

    async def acknowledge_update_notice(self, *, user_id: int, task_id: str) -> bool:
        return await self._notice_store.acknowledge(user_id=user_id, task_id=task_id)

    async def get_update_diagnostics(self, task_id: str) -> JSONDict:
        return await self._diagnostics_store.get_summary(task_id)

    async def update(self) -> ApplicationUpdateResult:
        self._deps.logging.logger.info("API request to initiate self-update received.")
        if self._deps.services.infrastructure.metrics_manager is not None:
            self._deps.services.infrastructure.metrics_manager.increment_counter(
                "global",
                "updates_triggered",
            )
        async with self._update_lock:
            prior_task_id = self._preparation_status.active_task_id
            accepted = False
            try:
                result = await self._transaction.run()
                accepted = result.outcome == "accepted"
                return result
            finally:
                if not accepted and self._preparation_status.active_task_id != prior_task_id:
                    self._preparation_status.finish()
