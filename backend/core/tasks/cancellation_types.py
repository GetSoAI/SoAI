"""SoAI - Task cancellation result dataclasses [backend/core/tasks/cancellation_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "AddTokenResult",
    "CancelAllResult",
    "ClearScopeResult",
    "HistorySnapshot",
    "RecordCancellationResult",
    "RemoveTokenResult",
    "SweepResult",
)


@dataclass(frozen=True, slots=True)
class AddTokenResult:
    added: bool
    scope_id: str


@dataclass(frozen=True, slots=True)
class RemoveTokenResult:
    removed: bool
    scope_cleared: bool
    remaining_tokens: int


@dataclass(frozen=True, slots=True)
class ClearScopeResult:
    removed_tokens: int
    scope_cleared: bool


@dataclass(frozen=True, slots=True)
class SweepResult:
    removed_tokens: int
    cleared_scopes: int
    remaining_scopes: int


@dataclass(frozen=True, slots=True)
class RecordCancellationResult:
    recorded: bool
    reason: str


@dataclass(frozen=True, slots=True)
class HistorySnapshot:
    cancelled_reasons: dict[str, str]
    cancelled_order: list[str]
    max_history: int


@dataclass(frozen=True, slots=True)
class CancelAllResult:
    cancellations_targeted: int
    cancellation_ids: list[str]
    excluded_cancellation_ids: list[str]
    reason: str
    include_internal: bool
    newly_cancelled_ids: list[str]
