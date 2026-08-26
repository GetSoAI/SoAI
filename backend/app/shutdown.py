"""SoAI - Application graceful shutdown orchestration and sequencing [backend/app/shutdown.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.lifecycle.budgets import LifecycleShutdownBudgets
from app.lifecycle.runner import LifecycleRunner
from app.lifecycle.shutdown_infrastructure_plan import (
    build_hardware_shutdown_entries,
    build_pre_shutdown_quiesce_entries,
)
from app.lifecycle.shutdown_stage_runner import (
    run_shutdown_stage_continue,
    run_sync_shutdown_stage_continue,
)
from app.shutdown_components import shutdown_components
from app.shutdown_infrastructure import (
    await_task_finalizers,
    shutdown_event_bus,
    shutdown_http_client_and_database,
)
from app.types_application import ApplicationContext
from core.backup.types import BackupCreateResult
from core.browser.playwright_installation import shutdown_playwright_install_executor
from core.concurrency.bounded_blocking import shutdown_bounded_pool_executor
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.filesystem.async_read import shutdown_file_read_executor
from core.network.dns import shutdown_dns_executor
from core.tasks.task_cancellation_ops import cancel_task
from mcp.rag.scraper.html_parse_executor import shutdown_html_parse_executor
from terminal.pty_loops import shutdown_pty_read_executor

__all__ = (
    "ApplicationShutdownCoordinator",
    "ApplicationShutdownCoordinatorDependencies",
)

OPERATION = "application_shutdown.run_shutdown_sequence"


@dataclass(frozen=True, slots=True)
class ApplicationShutdownCoordinatorDependencies:
    def __post_init__(self) -> None:
        require_dependencies(owner="ApplicationShutdownCoordinatorDependencies")


async def _run_shutdown_backup_if_configured(
    *,
    application_context: ApplicationContext,
    backup_timeout_sec: float,
) -> None:
    if backup_timeout_sec <= 0:
        return
    backup_service = application_context.services.storage.backup_service
    backup_task: asyncio.Task[BackupCreateResult | None] | None = None
    try:
        application_context.logging.logger.info("Running shutdown backup...")
        backup_task = create_ephemeral_task(
            backup_service.create_backup(),
            name="shutdown-backup",
        )
        await asyncio.wait_for(backup_task, timeout=backup_timeout_sec)
    except TimeoutError:
        application_context.logging.logger.warning(
            "Shutdown backup exceeded timeout of %.1fs and will be cancelled.",
            backup_timeout_sec,
        )
        await cancel_task(
            backup_task,
            logger=application_context.logging.logger,
            label="shutdown-backup",
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="application_shutdown.run_shutdown_sequence",
        )
        log_exception(
            application_context.logging.logger,
            coerced,
            message="Shutdown backup failed",
            operation=OPERATION,
        )
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            application_context.logging.logger,
            coerced,
            message="Unexpected shutdown backup failure",
            operation=OPERATION,
        )


async def _shutdown_communications_sync_actor_early(
    *,
    application_context: ApplicationContext,
    timeout_sec: float,
) -> None:
    application_context.logging.logger.debug(
        "Quiescing Communications Sync Actor before shutdown coordination.",
    )
    entries = build_pre_shutdown_quiesce_entries(
        application_context,
        component_timeout_sec=timeout_sec,
    )
    await LifecycleRunner(logger=application_context.logging.logger).run_entries_continue(entries)


async def _run_shutdown_cancellation(
    *,
    application_context: ApplicationContext,
) -> None:
    if application_context.runtime.prune_tokens_task and (
        not application_context.runtime.prune_tokens_task.done()
    ):
        await cancel_task(
            application_context.runtime.prune_tokens_task,
            logger=application_context.logging.logger,
            label="prune-webui-session-state",
        )
        application_context.runtime.set_prune_tokens_task(None)


def _shutdown_webui_login_password_executor(application_context: ApplicationContext) -> None:
    shutdown_bounded_pool_executor(application_context.api_runtime_singletons.login_password_pool)


def _shutdown_prompt_token_counter(application_context: ApplicationContext) -> None:
    application_context.services.infrastructure.prompt_token_counter.shutdown()


async def _clear_hardware_dirty_flag_and_shutdown_executors(
    *,
    application_context: ApplicationContext,
    timeout_sec: float,
) -> None:
    try:
        entries = build_hardware_shutdown_entries(
            application_context,
            component_timeout_sec=timeout_sec,
        )
        await LifecycleRunner(logger=application_context.logging.logger).run_entries_continue(
            entries,
        )
    finally:
        run_sync_shutdown_stage_continue(
            application_context=application_context,
            component_name="PTY Read Executor",
            action=shutdown_pty_read_executor,
        )
        run_sync_shutdown_stage_continue(
            application_context=application_context,
            component_name="DNS Executor",
            action=shutdown_dns_executor,
        )
        run_sync_shutdown_stage_continue(
            application_context=application_context,
            component_name="File Read Executor",
            action=shutdown_file_read_executor,
        )
        run_sync_shutdown_stage_continue(
            application_context=application_context,
            component_name="HTML Parse Executor",
            action=shutdown_html_parse_executor,
        )
        run_sync_shutdown_stage_continue(
            application_context=application_context,
            component_name="Playwright Install Executor",
            action=shutdown_playwright_install_executor,
        )
        run_sync_shutdown_stage_continue(
            application_context=application_context,
            component_name="WebUI Login Password Executor",
            action=lambda: _shutdown_webui_login_password_executor(application_context),
        )
        run_sync_shutdown_stage_continue(
            application_context=application_context,
            component_name="Prompt Token Counter",
            action=lambda: _shutdown_prompt_token_counter(application_context),
        )


class ApplicationShutdownCoordinator:
    def __init__(self, deps: ApplicationShutdownCoordinatorDependencies) -> None:
        self._deps = deps

    async def run_shutdown_sequence(
        self,
        *,
        application_context: ApplicationContext,
        budgets: LifecycleShutdownBudgets,
    ) -> None:
        try:
            await run_shutdown_stage_continue(
                application_context=application_context,
                component_name="Communications Sync Actor Pre-Shutdown",
                awaitable=_shutdown_communications_sync_actor_early(
                    application_context=application_context,
                    timeout_sec=budgets.component_timeout_sec,
                ),
            )
            await run_shutdown_stage_continue(
                application_context=application_context,
                component_name="Shutdown Backup",
                awaitable=_run_shutdown_backup_if_configured(
                    application_context=application_context,
                    backup_timeout_sec=budgets.backup_timeout_sec,
                ),
            )
            await run_shutdown_stage_continue(
                application_context=application_context,
                component_name="Shutdown Cancellation",
                awaitable=_run_shutdown_cancellation(
                    application_context=application_context,
                ),
            )
            await run_shutdown_stage_continue(
                application_context=application_context,
                component_name="Application Components",
                awaitable=shutdown_components(
                    application_context=application_context,
                    logger=application_context.logging.logger,
                    budgets=budgets,
                ),
            )
            await run_shutdown_stage_continue(
                application_context=application_context,
                component_name="Event Bus",
                awaitable=shutdown_event_bus(
                    application_context=application_context,
                    timeout_sec=budgets.component_timeout_sec,
                ),
            )
            await run_shutdown_stage_continue(
                application_context=application_context,
                component_name="HTTP Client and Database",
                awaitable=shutdown_http_client_and_database(
                    application_context=application_context,
                    timeout_sec=budgets.component_timeout_sec,
                ),
            )
            await run_shutdown_stage_continue(
                application_context=application_context,
                component_name="Task Finalizers",
                awaitable=await_task_finalizers(
                    application_context=application_context,
                    timeout_sec=budgets.finalizer_timeout_sec,
                ),
            )
        finally:
            await run_shutdown_stage_continue(
                application_context=application_context,
                component_name="Hardware Dirty Flag and Executors",
                awaitable=_clear_hardware_dirty_flag_and_shutdown_executors(
                    application_context=application_context,
                    timeout_sec=budgets.component_timeout_sec,
                ),
            )
