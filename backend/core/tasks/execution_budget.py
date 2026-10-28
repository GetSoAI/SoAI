"""SoAI - Phase-independent inference execution budget and deadline ownership [backend/core/tasks/execution_budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from core.concurrency.deadlines import MonotonicDeadline
from core.types.json import JSONValue

__all__ = (
    "ExecutionBudget",
    "ExecutionBudgetSource",
    "ExecutionLimit",
    "earliest_execution_budget",
    "resolve_execution_limit",
)


class ExecutionBudgetSource(StrEnum):
    CALLER_REQUEST = "caller_request"
    PLUGIN_HEALTH = "plugin_health"


@dataclass(frozen=True, slots=True)
class ExecutionLimit:
    seconds: float
    source: ExecutionBudgetSource
    health_seconds: float
    caller_seconds: float | None = None


def resolve_execution_limit(health_seconds: float, caller_seconds: float | None) -> ExecutionLimit:
    if caller_seconds is not None and caller_seconds < health_seconds:
        return ExecutionLimit(
            caller_seconds, ExecutionBudgetSource.CALLER_REQUEST, health_seconds, caller_seconds
        )
    return ExecutionLimit(
        health_seconds, ExecutionBudgetSource.PLUGIN_HEALTH, health_seconds, caller_seconds
    )


@dataclass(frozen=True, slots=True)
class ExecutionBudget:
    started_monotonic: float
    deadline: MonotonicDeadline
    source: ExecutionBudgetSource
    health_check_config: Mapping[str, JSONValue] | None = field(
        default=None, compare=False, hash=False
    )
    generation: int = 0
    caller_deadline: MonotonicDeadline | None = None
    caller_seconds: float | None = None

    @classmethod
    def start(
        cls,
        limit: ExecutionLimit,
        *,
        health_check_config: Mapping[str, JSONValue] | None = None,
        generation: int = 0,
        previous: ExecutionBudget | None = None,
    ) -> ExecutionBudget:
        started_monotonic = time.monotonic()
        caller_seconds = previous.caller_seconds if previous is not None else limit.caller_seconds
        if caller_seconds is None and limit.source is ExecutionBudgetSource.CALLER_REQUEST:
            caller_seconds = limit.seconds
        caller_deadline = previous.caller_deadline if previous is not None else None
        if caller_deadline is None and caller_seconds is not None:
            caller_deadline = MonotonicDeadline(started_monotonic + max(0.0, caller_seconds))
        deadline = MonotonicDeadline(started_monotonic + max(0.0, limit.health_seconds))
        source = ExecutionBudgetSource.PLUGIN_HEALTH
        if (
            caller_deadline is not None
            and caller_deadline.deadline_monotonic < deadline.deadline_monotonic
        ):
            deadline = caller_deadline
            source = ExecutionBudgetSource.CALLER_REQUEST
            started_monotonic = deadline.deadline_monotonic - (caller_seconds or 0.0)
        return cls(
            started_monotonic,
            deadline,
            source,
            (
                MappingProxyType(dict(health_check_config))
                if health_check_config is not None
                else None
            ),
            generation,
            caller_deadline,
            caller_seconds,
        )

    @property
    def budget_seconds(self) -> float:
        return max(0.0, self.deadline.deadline_monotonic - self.started_monotonic)


def earliest_execution_budget(
    current: ExecutionBudget | None, incoming: ExecutionBudget | None
) -> ExecutionBudget | None:
    if current is None or incoming is None:
        return current if incoming is None else incoming
    if current.generation != incoming.generation:
        return current if current.generation > incoming.generation else incoming
    current_deadline = current.deadline.deadline_monotonic
    incoming_deadline = incoming.deadline.deadline_monotonic
    if current_deadline != incoming_deadline:
        return current if current_deadline < incoming_deadline else incoming
    if current.source is not incoming.source:
        return current if current.source is ExecutionBudgetSource.PLUGIN_HEALTH else incoming
    return current if current.started_monotonic <= incoming.started_monotonic else incoming
