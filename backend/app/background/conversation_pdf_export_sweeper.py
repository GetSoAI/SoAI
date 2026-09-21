"""SoAI - Periodic conversation PDF export artifact sweeper [backend/app/background/conversation_pdf_export_sweeper.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.browser.pdf_font_manifest import resolve_pdf_font_cache_root
from core.browser.pdf_font_staging import prune_pdf_font_cache
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.progress import (
    await_background_task_shutdown,
    run_background_periodic_task,
)
from core.timing.constants import LONG_IDLE_TIMEOUT_SEC
from features.conversation_export.retention import sweep_conversation_pdf_export_artifacts
from features.conversation_export.settings import resolve_conversation_pdf_export_settings

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from features.conversation_export.settings import ConversationPdfExportSettings

__all__ = (
    "ConversationPdfExportSweeper",
    "ConversationPdfExportSweeperDependencies",
)

LOGGER_NAME = "SoAI.app.background.conversation_pdf_export_sweeper"
OPERATION = "app.background.conversation_pdf_export_sweeper.cleanup"


@dataclass(frozen=True, slots=True)
class ConversationPdfExportSweeperDependencies:
    config: ConfigProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ConversationPdfExportSweeperDependencies",
            cancellation_binder=self.cancellation_binder,
            config=self.config,
            finalizer_tracker=self.finalizer_tracker,
        )


class ConversationPdfExportSweeper:
    def __init__(self, deps: ConversationPdfExportSweeperDependencies) -> None:
        self._deps = deps
        self._logger = get_logger(LOGGER_NAME)
        self._shutdown_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        active_task = self._task
        if active_task is not None and not active_task.done():
            return
        self._shutdown_event = asyncio.Event()
        self._task = None
        settings = resolve_conversation_pdf_export_settings(self._deps.config)

        async def _run_once() -> None:
            await self._run_once(settings)

        self._task = run_background_periodic_task(
            shutdown_event=self._shutdown_event,
            interval_seconds=float(LONG_IDLE_TIMEOUT_SEC),
            task=_run_once,
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            cancellation_id=create_system_id(
                subsystem="conversation_pdf_export",
                owner="artifact_sweeper",
                include_random_suffix=False,
            ),
            owner="conversation_pdf_export",
            name="conversation-pdf-export-sweeper",
            logger=self._logger,
            metadata={
                "interval_ms": LONG_IDLE_TIMEOUT_SEC * 1000,
                "retention_sec": settings.artifact_retention_sec,
            },
            task_name="conversation_pdf_export_artifact_cleanup",
            run_immediately=True,
        )

    async def _run_once(self, settings: ConversationPdfExportSettings) -> None:
        try:
            removed_directories = await asyncio.to_thread(
                sweep_conversation_pdf_export_artifacts,
                temp_dir=settings.temp_dir,
                retention_sec=settings.artifact_retention_sec,
            )
            pruned_fonts = await asyncio.to_thread(
                prune_pdf_font_cache,
                resolve_pdf_font_cache_root(),
            )
            if removed_directories or pruned_fonts:
                self._logger.debug(
                    "Cleaned up conversation PDF exports: artifacts=%s, cached_fonts=%s.",
                    removed_directories,
                    pruned_fonts,
                )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Conversation PDF export artifact cleanup failed.",
                operation=OPERATION,
                level="warning",
            )

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        task, self._task = self._task, None
        await await_background_task_shutdown(
            task,
            logger=self._logger,
            operation="app.background.conversation_pdf_export_sweeper.shutdown",
            message=("Conversation PDF export sweeper task failed during shutdown (non-critical)."),
            level="debug",
        )
