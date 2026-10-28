"""SoAI - Active update preparation status [backend/app/updater/software_update/preparation_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.updater.software_update.preparation_progress import read_preparation_progress
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("UpdatePreparationStatus",)

OPERATION_UPDATE_PREPARATION_STATUS = "application_update_service.get_preparation_status"


class UpdatePreparationStatus:
    def __init__(self, base_path: str, logger: LoggerProtocol) -> None:
        self._base_path = base_path
        self._logger = logger
        self._active_task_id: str | None = None
        self._last_progress: JSONDict | None = None
        self._failure_reported = False
        self._read_lock = asyncio.Lock()

    def begin(self, task_id: str) -> None:
        self._active_task_id = task_id
        self._last_progress = None
        self._failure_reported = False

    @property
    def active_task_id(self) -> str | None:
        return self._active_task_id

    def finish(self) -> None:
        self._active_task_id = None

    async def get_status(self) -> JSONDict:
        async with self._read_lock:
            task_id = self._active_task_id
            if task_id is None:
                return {"active": False}
            try:
                progress = await asyncio.to_thread(
                    read_preparation_progress, self._base_path, task_id
                )
            except (OSError, SoAIError, ValueError) as exception:
                if self._active_task_id != task_id:
                    return {"active": False}
                if not self._failure_reported:
                    log_exception(
                        self._logger,
                        exception,
                        message="Update preparation progress is unavailable.",
                        operation=OPERATION_UPDATE_PREPARATION_STATUS,
                    )
                    self._failure_reported = True
                return {
                    "active": True,
                    **(self._last_progress or {}),
                    "task_id": task_id,
                    "phase": "unavailable",
                }
            if self._active_task_id != task_id:
                return {"active": False}
            if progress is None:
                return {
                    "active": True,
                    **(self._last_progress or {}),
                    "task_id": task_id,
                    "phase": "unavailable" if self._last_progress is not None else "preparing",
                }
            self._failure_reported = False
            self._last_progress = progress
            return {"active": True, **progress}
