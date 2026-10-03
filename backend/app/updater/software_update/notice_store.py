"""SoAI - Serialized per-user software update notice access [backend/app/updater/software_update/notice_store.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.tasks.software_update_notice import (
    SoftwareUpdateNotice,
    acknowledge_software_update_notice,
    read_software_update_notice,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("SoftwareUpdateNoticeStore",)

OPERATION_READ_UPDATE_NOTICE = "application_update_service.read_update_notice"


class SoftwareUpdateNoticeStore:
    def __init__(self, base_path: str, logger: LoggerProtocol) -> None:
        self._base_path = base_path
        self._logger = logger
        self._lock = asyncio.Lock()

    async def get_pending_notice(self, user_id: int) -> JSONDict | None:
        async with self._lock:
            notice = await asyncio.to_thread(self._read_notice)
        if notice is None or notice.is_acknowledged_by(user_id):
            return None
        return notice.to_public_payload()

    async def acknowledge(self, *, user_id: int, task_id: str) -> bool:
        async with self._lock:
            return await asyncio.to_thread(
                acknowledge_software_update_notice,
                self._base_path,
                task_id=task_id,
                user_id=user_id,
            )

    def _read_notice(self) -> SoftwareUpdateNotice | None:
        try:
            return read_software_update_notice(self._base_path)
        except (OSError, SoAIError) as exception:
            log_exception(
                self._logger,
                exception,
                message="Software update notice is unavailable.",
                operation=OPERATION_READ_UPDATE_NOTICE,
                level="warning",
            )
            return None
