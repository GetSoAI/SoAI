"""SoAI - SQLite WAL lineage integrity guard [backend/database/core/wal_lineage_guard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import time
from collections.abc import Callable

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger

__all__ = ("WalLineageGuard",)

LOGGER_NAME = "SoAI.database.core.wal_lineage_guard"
OPERATION_ESCALATE = "database.core.wal_lineage_guard.escalate"


class WalLineageGuard:
    def __init__(
        self,
        db_file_paths: tuple[str, str, str],
        *,
        is_shared_memory_mode: bool,
        check_interval_sec: float = 1.0,
    ) -> None:
        self._db_file_paths = db_file_paths
        self._enabled = not is_shared_memory_mode
        self._check_interval_sec = check_interval_sec
        self._baseline: dict[str, tuple[int, int]] = {}
        self._last_check_monotonic: float = 0.0
        self._escalation: Callable[[str], None] | None = None

    def bind_escalation(self, escalation: Callable[[str], None]) -> None:
        self._escalation = escalation

    @staticmethod
    def _stat_identity(path: str) -> tuple[int, int] | None:
        try:
            file_stat = os.stat(path)
        except OSError:
            return None
        return (file_stat.st_dev, file_stat.st_ino)

    def capture_baseline(self) -> None:
        if not self._enabled:
            return
        baseline: dict[str, tuple[int, int]] = {}
        for path in self._db_file_paths:
            identity = self._stat_identity(path)
            if identity is not None:
                baseline[path] = identity
        self._baseline = baseline
        self._last_check_monotonic = time.monotonic()

    def find_violations(self) -> tuple[str, ...]:
        if not self._enabled or not self._baseline:
            return ()
        now = time.monotonic()
        if now - self._last_check_monotonic < self._check_interval_sec:
            return ()
        self._last_check_monotonic = now
        violations: list[str] = []
        for path in self._db_file_paths:
            identity = self._stat_identity(path)
            baseline_identity = self._baseline.get(path)
            if baseline_identity is None:
                if identity is not None:
                    self._baseline[path] = identity
                continue
            if identity is None:
                violations.append(f"{path} was deleted while the writer session is active")
            elif identity != baseline_identity:
                violations.append(
                    f"{path} was replaced while the writer session is active (file identity changed)",
                )
        return tuple(violations)

    def refresh_after_rotation(self) -> tuple[str, ...]:
        if not self._enabled:
            return ()
        database_path = self._db_file_paths[0]
        baseline_identity = self._baseline.get(database_path)
        current_identity = self._stat_identity(database_path)
        if baseline_identity is None:
            return (f"{database_path} has no active writer-session identity baseline",)
        if current_identity is None:
            return (f"{database_path} was deleted during WAL lifecycle rotation",)
        if current_identity != baseline_identity:
            return (
                f"{database_path} was replaced during WAL lifecycle rotation (file identity changed)",
            )
        for sidecar_path in self._db_file_paths[1:]:
            self._baseline.pop(sidecar_path, None)
            sidecar_identity = self._stat_identity(sidecar_path)
            if sidecar_identity is not None:
                self._baseline[sidecar_path] = sidecar_identity
        self._last_check_monotonic = time.monotonic()
        return ()

    def escalate(self, reason: str) -> None:
        logger = get_logger(LOGGER_NAME)
        logger.critical(
            "FATAL: SQLite WAL lineage violation: %s. Halting the writer session and requesting an application restart to reopen a single healthy database lineage.",
            reason,
        )
        escalation = self._escalation
        if escalation is None:
            logger.critical(
                "No WAL lineage escalation is bound; the writer session halts without an automatic application restart.",
            )
            return
        try:
            escalation(reason)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="WAL lineage escalation callback failed.",
                operation=OPERATION_ESCALATE,
                level="critical",
            )
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=OPERATION_ESCALATE)
            log_exception(
                logger,
                coerced,
                message="WAL lineage escalation callback failed unexpectedly.",
                operation=OPERATION_ESCALATE,
                level="critical",
            )
