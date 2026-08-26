"""SoAI - Database lifecycle shutdown entry construction [backend/app/lifecycle/database_shutdown_entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.lifecycle.entries import LifecycleEntry
from app.lifecycle.runner import LifecycleRunner
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.logging.protocols import LoggerProtocol
from core.timing.constants import CONTROL_TIMEOUT_SEC
from database.core.core import DatabaseCore

__all__ = (
    "cleanup_database_core_after_build_failure",
    "database_shutdown_entries",
    "report_database_build_failure",
)

_OPERATION_BUILD_DATABASE_SERVICES = "app.composition.build_database.build_database_services"


def database_shutdown_entries(
    *,
    database_core: DatabaseCore,
    phase: str,
    timeout_sec: float,
    critical: bool,
) -> tuple[LifecycleEntry, ...]:
    return (
        LifecycleEntry(
            component_name="Database Vacuum",
            phase=phase,
            action=database_core.vacuum.shutdown,
            timeout_sec=timeout_sec,
            critical=critical,
        ),
        LifecycleEntry(
            component_name="Database Reader",
            phase=phase,
            action=database_core.reader.shutdown,
            timeout_sec=timeout_sec,
            critical=critical,
        ),
        LifecycleEntry(
            component_name="Database Writer",
            phase=phase,
            action=database_core.writer.shutdown,
            timeout_sec=timeout_sec,
            critical=critical,
        ),
    )


async def cleanup_database_core_after_build_failure(
    database_core: DatabaseCore,
    logger: LoggerProtocol,
) -> None:
    entries = database_shutdown_entries(
        database_core=database_core,
        phase="database_build_failure_cleanup",
        timeout_sec=CONTROL_TIMEOUT_SEC,
        critical=False,
    )
    failures = await LifecycleRunner(logger=logger).run_entries_continue(entries)
    if failures:
        logger.critical(
            "Database build failure cleanup completed with %d failure(s).",
            len(failures),
        )


async def report_database_build_failure(
    database_core: DatabaseCore,
    exception: BaseException,
    logger: LoggerProtocol,
) -> None:
    coerced = coerce_to_soai_error(
        exception,
        operation=_OPERATION_BUILD_DATABASE_SERVICES,
    )
    log_exception(
        logger,
        coerced,
        message="Database services build failed; running cleanup.",
        operation=_OPERATION_BUILD_DATABASE_SERVICES,
        level="critical",
    )
    await cleanup_database_core_after_build_failure(database_core, logger)
