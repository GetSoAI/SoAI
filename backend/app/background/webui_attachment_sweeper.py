"""SoAI - Periodic WebUI attachment cleanup sweeper [backend/app/background/webui_attachment_sweeper.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.background.webui_attachment_cleanup_run import run_webui_attachment_cleanup
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.storage_root_resolution import resolve_managed_files_storage_root
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.progress import (
    await_background_task_shutdown,
    run_background_periodic_task,
)
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.attachments.protocols_database import (
        DatabaseConversationAttachmentsProtocol,
        DatabaseConversationKnowledgeAttachmentsProtocol,
    )
    from core.database.protocols import DatabaseCoreProtocol
    from core.events.protocols import EventBusProtocol
    from core.plugins.protocols_instance import FilesProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = ("WebuiAttachmentSweeper", "WebuiAttachmentSweeperDependencies")

LOGGER_NAME = "SoAI.app.background.webui_attachment_sweeper"
OPERATION = "app.background.webui_attachment_sweeper.cleanup"
_BATCH_LIMIT = 500


@dataclass(frozen=True, slots=True)
class WebuiAttachmentSweeperDependencies:
    config: ConfigProtocol
    files: FilesProtocol
    database_core: DatabaseCoreProtocol
    database_attachments: DatabaseConversationAttachmentsProtocol
    database_knowledge: DatabaseConversationKnowledgeAttachmentsProtocol
    event_bus: EventBusProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="WebuiAttachmentSweeperDependencies",
            cancellation_binder=self.cancellation_binder,
            config=self.config,
            database_core=self.database_core,
            database_attachments=self.database_attachments,
            database_knowledge=self.database_knowledge,
            event_bus=self.event_bus,
            files=self.files,
            finalizer_tracker=self.finalizer_tracker,
        )


class WebuiAttachmentSweeper:
    def __init__(self, deps: WebuiAttachmentSweeperDependencies) -> None:
        self._deps = deps
        self._logger = get_logger(LOGGER_NAME)
        self._shutdown_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._shutdown_event = asyncio.Event()
        self._task = None
        storage_root = resolve_managed_files_storage_root(self._deps.config, self._deps.files)

        async def _run_once() -> None:
            await self._run_once(storage_root)

        self._task = run_background_periodic_task(
            shutdown_event=self._shutdown_event,
            interval_seconds=float(LONG_REQUEST_TIMEOUT_SEC),
            task=_run_once,
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            cancellation_id=create_system_id(
                subsystem="webui_attachment",
                owner="cleanup_sweeper",
                include_random_suffix=False,
            ),
            owner="webui_attachments",
            name="webui-attachment-sweeper",
            logger=self._logger,
            metadata={"interval_ms": LONG_REQUEST_TIMEOUT_SEC * 1000, "batch_limit": _BATCH_LIMIT},
            task_name="webui_attachment_cleanup",
            run_immediately=False,
        )

    async def _run_once(self, storage_root: str) -> None:
        try:
            physical_count, knowledge_count = await run_webui_attachment_cleanup(
                database_core=self._deps.database_core,
                database_attachments=self._deps.database_attachments,
                database_knowledge=self._deps.database_knowledge,
                event_bus=self._deps.event_bus,
                logger=self._logger,
                storage_root=storage_root,
                batch_limit=_BATCH_LIMIT,
            )
            if physical_count or knowledge_count:
                self._logger.info(
                    "Cleaned up WebUI attachments: physical=%s, knowledge=%s.",
                    physical_count,
                    knowledge_count,
                )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="WebUI attachment cleanup failed.",
                operation=OPERATION,
                level="warning",
            )

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        task = self._task
        self._task = None
        await await_background_task_shutdown(
            task,
            logger=self._logger,
            operation="app.background.webui_attachment_sweeper.shutdown",
            message="WebUI attachment sweeper task failed during shutdown (non-critical).",
            level="debug",
        )
