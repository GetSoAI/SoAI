"""SoAI - Lifecycle shutdown budget resolution [backend/app/lifecycle/budgets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.lifecycle.shutdown_budget_counts import SHUTDOWN_COMPONENT_TIMEOUT_ENTRY_COUNT
from core.config.numeric import coerce_positive_float
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.validation.booleans import parse_bool

__all__ = (
    "DEFAULT_SHUTDOWN_WATCHDOG_TIMEOUT_SEC",
    "LifecycleShutdownBudgets",
    "resolve_lifecycle_shutdown_budgets",
)

DEFAULT_SHUTDOWN_WATCHDOG_TIMEOUT_SEC = 1050.0


@dataclass(frozen=True, slots=True)
class LifecycleShutdownBudgets:
    quiesce_period_sec: float
    server_drain_timeout_sec: float
    component_timeout_sec: float
    task_registry_timeout_sec: float
    orchestrator_timeout_sec: float
    mcp_timeout_sec: float
    finalizer_timeout_sec: float
    force_cleanup_timeout_sec: float
    watchdog_timeout_sec: float
    backup_timeout_sec: float

    @property
    def graceful_budget_sec(self) -> float:
        return (
            self.quiesce_period_sec
            + self.server_drain_timeout_sec
            + self.backup_timeout_sec
            + self.component_timeout_sec * SHUTDOWN_COMPONENT_TIMEOUT_ENTRY_COUNT
            + self.task_registry_timeout_sec
            + self.orchestrator_timeout_sec
            + self.mcp_timeout_sec
            + self.finalizer_timeout_sec
            + self.force_cleanup_timeout_sec
        )


def _timeout(config: ConfigProtocol, key: str, default: float, minimum: float = 0.0) -> float:
    return coerce_positive_float(
        config.get(key, default),
        default=default,
        minimum=minimum,
    )


def resolve_lifecycle_shutdown_budgets(config: ConfigProtocol) -> LifecycleShutdownBudgets:
    budgets = LifecycleShutdownBudgets(
        quiesce_period_sec=_timeout(config, "SYSTEM.SHUTDOWN.QUIESCE_PERIOD_SEC", 3.0),
        server_drain_timeout_sec=_timeout(
            config,
            "SYSTEM.SHUTDOWN.SERVER_DRAIN_TIMEOUT_SEC",
            config.get_float("SERVER.HTTP.NETWORK.SHUTDOWN_TIMEOUT_SEC"),
        ),
        component_timeout_sec=_timeout(config, "SYSTEM.SHUTDOWN.COMPONENT_TIMEOUT_SEC", 20.0),
        task_registry_timeout_sec=_timeout(
            config,
            "SYSTEM.SHUTDOWN.TASK_REGISTRY_TIMEOUT_SEC",
            150.0,
        ),
        orchestrator_timeout_sec=_timeout(config, "SYSTEM.SHUTDOWN.ORCHESTRATOR_TIMEOUT_SEC", 75.0),
        mcp_timeout_sec=_timeout(config, "SYSTEM.SHUTDOWN.MCP_TIMEOUT_SEC", 60.0),
        finalizer_timeout_sec=_timeout(config, "SYSTEM.SHUTDOWN.FINALIZER_TIMEOUT_SEC", 10.0),
        force_cleanup_timeout_sec=_timeout(
            config,
            "SYSTEM.SHUTDOWN.FORCE_CLEANUP_TIMEOUT_SEC",
            5.0,
        ),
        watchdog_timeout_sec=_timeout(
            config,
            "SYSTEM.SHUTDOWN.WATCHDOG_TIMEOUT_SEC",
            DEFAULT_SHUTDOWN_WATCHDOG_TIMEOUT_SEC,
            1.0,
        ),
        backup_timeout_sec=_shutdown_backup_timeout(config),
    )
    if budgets.watchdog_timeout_sec <= budgets.graceful_budget_sec:
        raise ValidationError(
            "SYSTEM.SHUTDOWN.WATCHDOG_TIMEOUT_SEC must exceed the computed graceful shutdown budget.",
            details={
                "watchdog_timeout_sec": budgets.watchdog_timeout_sec,
                "graceful_budget_sec": budgets.graceful_budget_sec,
            },
        )
    return budgets


def _shutdown_backup_timeout(config: ConfigProtocol) -> float:
    if not parse_bool(config.get("DATA.BACKUP.ENABLED", False), default=False):
        return 0.0
    if not parse_bool(config.get("DATA.BACKUP.SCHEDULE.ON_SHUTDOWN", False), default=False):
        return 0.0
    return _timeout(config, "DATA.BACKUP.SCHEDULE.ON_SHUTDOWN_TIMEOUT_SEC", 120.0, 10.0)
