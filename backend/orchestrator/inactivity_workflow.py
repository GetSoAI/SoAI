"""SoAI - Inactivity monitor action workflow helpers [backend/orchestrator/inactivity_workflow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.trace_logging import TRACE_LEVEL
from core.metrics.keyspace_base import INACTIVITY_MONITOR_COUNTER_ACTIONS_TRIGGERED

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.types.json import JSONValue

__all__ = (
    "InactivityActionSpec",
    "run_inactivity_workflow",
)


@dataclass(frozen=True, slots=True)
class InactivityActionSpec:
    log_level: str
    message: str
    audit_action: str
    audit_target: str
    audit_reason: str
    metrics_label: str


async def run_inactivity_workflow(
    *,
    logger: LoggerProtocol,
    audit_logger: LoggerProtocol,
    metrics_manager: MetricsManagerProtocol,
    timeout: float,
    action_spec: InactivityActionSpec,
    finalizer: Callable[[], Awaitable[None]],
    execute_inactivity_action: Callable[[float, Callable[[], Awaitable[None]]], Awaitable[None]],
) -> None:
    async def action() -> None:
        log_level = action_spec.log_level
        if log_level == "trace":
            logger.log(TRACE_LEVEL, action_spec.message)
        elif log_level == "debug":
            logger.debug(action_spec.message)
        elif log_level == "info":
            logger.info(action_spec.message)
        elif log_level in {"warn", "warning"}:
            logger.warning(action_spec.message)
        elif log_level == "error":
            logger.error(action_spec.message)
        elif log_level in {"critical", "fatal"}:
            logger.critical(action_spec.message)
        else:
            raise ValueError(f"Unsupported log_level for inactivity workflow: {log_level}")
        details: dict[str, JSONValue] = {
            "reason": action_spec.audit_reason,
            "timeout_minutes": timeout / 60,
        }
        audit_logger.info(
            {
                "actor": "system",
                "action": action_spec.audit_action,
                "target": action_spec.audit_target,
                "details": details,
            },
        )
        metrics_manager.increment_counter(
            *INACTIVITY_MONITOR_COUNTER_ACTIONS_TRIGGERED,
            action_spec.metrics_label,
        )
        await finalizer()

    await execute_inactivity_action(timeout, action)
