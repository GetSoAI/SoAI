"""SoAI - Read-only software update diagnostics access [backend/app/updater/software_update/diagnostics_store.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.tasks.software_update_diagnostic_reports import (
    UpdateDiagnosticsSummary,
    read_update_diagnostics_summary,
    unavailable_update_diagnostics,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("SoftwareUpdateDiagnosticsStore",)

OPERATION_READ_UPDATE_DIAGNOSTICS = "application_update_service.read_update_diagnostics"


class SoftwareUpdateDiagnosticsStore:
    def __init__(self, base_path: str, logger: LoggerProtocol) -> None:
        self._base_path = base_path
        self._logger = logger

    async def get_summary(self, task_id: str) -> JSONDict:
        summary = await asyncio.to_thread(self._read_summary, task_id)
        return summary.to_public_payload(task_id)

    def _read_summary(self, task_id: str) -> UpdateDiagnosticsSummary:
        try:
            return read_update_diagnostics_summary(self._base_path, task_id)
        except (OSError, SoAIError) as exception:
            log_exception(
                self._logger,
                exception,
                message="Software update diagnostics are unavailable.",
                operation=OPERATION_READ_UPDATE_DIAGNOSTICS,
                details={"task_id": task_id},
                level="warning",
            )
            return unavailable_update_diagnostics()
