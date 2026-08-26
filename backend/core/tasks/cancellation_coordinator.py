"""SoAI - Cancellation coordination workflows [backend/core/tasks/cancellation_coordinator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.concurrency.deadlines import deadline_remaining
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError, ValidationError
from core.tasks.cancellation_ids import (
    normalize_cancellation_id,
    require_cancellation_id,
)
from core.tasks.cancellation_snapshot import build_cancellation_snapshot
from core.tasks.cancellation_types import CancelAllResult, SweepResult
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TokenCollectionProtocol,
)
from core.timing.constants import SHORT_POLL_INTERVAL_SEC

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "CancellationCoordinator",
    "CancellationCoordinatorDependencies",
)


@dataclass(frozen=True, slots=True)
class CancellationCoordinatorDependencies:
    token_collection: TokenCollectionProtocol
    history: CancellationHistoryProtocol
    event_bus: CancellationEventBusProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="CancellationCoordinatorDependencies",
            event_bus=self.event_bus,
            history=self.history,
            token_collection=self.token_collection,
        )


class CancellationCoordinator(CancellationCoordinatorProtocol):
    __slots__ = ("_event_bus", "_history", "_token_collection")

    def __init__(self, deps: CancellationCoordinatorDependencies) -> None:
        self._token_collection = deps.token_collection
        self._history = deps.history
        self._event_bus = deps.event_bus

    def _resolve_scopes_for_cancellation(
        self,
        *,
        cancellation_id: str,
        active_scopes: list[str],
    ) -> list[str]:
        resolved: list[str] = []
        seen: set[str] = set()
        for scope in active_scopes:
            if scope == cancellation_id or scope.startswith(f"{cancellation_id}::"):
                if scope in seen:
                    continue
                seen.add(scope)
                resolved.append(scope)
        if cancellation_id not in seen:
            resolved.insert(0, cancellation_id)
        return resolved

    def _resolve_excluded_scopes(
        self,
        *,
        exclude_cancellation_ids: tuple[str, ...],
        active_scopes: list[str],
    ) -> set[str]:
        excluded_scopes: set[str] = set()
        active_scope_set = set(active_scopes)
        for cancellation_id in exclude_cancellation_ids:
            normalized_id = normalize_cancellation_id(cancellation_id)
            if not normalized_id:
                continue
            if normalized_id in active_scope_set:
                excluded_scopes.add(normalized_id)
            for scope in active_scopes:
                if scope.startswith(f"{normalized_id}::"):
                    excluded_scopes.add(scope)
        return excluded_scopes

    @override
    async def cancel_scope(self, cancellation_id: str, reason: str) -> bool:
        normalized_id = require_cancellation_id(cancellation_id)
        normalized_reason = str(reason or "").strip() or "Cancelled"
        active_scopes = await self._token_collection.get_all_scope_ids(include_internal=True)
        scopes_to_cancel = self._resolve_scopes_for_cancellation(
            cancellation_id=normalized_id,
            active_scopes=active_scopes,
        )
        active_scope_set = set(active_scopes)
        any_new_record = False
        final_reason = normalized_reason
        for scope_id in scopes_to_cancel:
            record_result = await self._history.record_cancellation(
                scope_id,
                normalized_reason,
                active_scopes=active_scope_set,
            )
            if record_result.recorded:
                any_new_record = True
            final_reason = record_result.reason
        if not any_new_record:
            return False
        for scope_id in scopes_to_cancel:
            tokens = await self._token_collection.get_tokens_for_scope(scope_id)
            for token in tokens:
                token.cancel(final_reason)
        await self._event_bus.publish_event("cancellation_recorded", normalized_id)
        return True

    @override
    async def cancel_all_scopes(
        self,
        reason: str,
        *,
        include_internal: bool,
        exclude_cancellation_ids: tuple[str, ...] = (),
        wait_for_release_timeout: float | None = None,
    ) -> CancelAllResult:
        normalized_reason = str(reason or "").strip()
        if not normalized_reason:
            raise ValidationError("A cancellation reason must be provided.")
        if wait_for_release_timeout is not None and wait_for_release_timeout < 0:
            raise ValidationError("Cancellation release timeout cannot be negative.")
        cancellation_ids = await self._token_collection.get_all_scope_ids(
            include_internal=include_internal,
        )
        excluded_scopes = self._resolve_excluded_scopes(
            exclude_cancellation_ids=exclude_cancellation_ids,
            active_scopes=cancellation_ids,
        )
        cancellation_ids_to_cancel = [
            cancellation_id
            for cancellation_id in cancellation_ids
            if cancellation_id not in excluded_scopes
        ]
        newly_cancelled: list[str] = []
        for cancellation_id in cancellation_ids_to_cancel:
            if await self.cancel_scope(cancellation_id, normalized_reason):
                newly_cancelled.append(cancellation_id)
        result = CancelAllResult(
            cancellations_targeted=len(cancellation_ids_to_cancel),
            cancellation_ids=list(cancellation_ids_to_cancel),
            excluded_cancellation_ids=sorted(excluded_scopes),
            reason=normalized_reason,
            include_internal=include_internal,
            newly_cancelled_ids=newly_cancelled,
        )
        if wait_for_release_timeout is None:
            return result
        await self._await_scope_releases(
            reason=normalized_reason,
            include_internal=include_internal,
            exclude_cancellation_ids=exclude_cancellation_ids,
            timeout=wait_for_release_timeout,
            targeted_ids=cancellation_ids_to_cancel,
            newly_cancelled_ids=newly_cancelled,
        )
        return CancelAllResult(
            cancellations_targeted=len(cancellation_ids_to_cancel),
            cancellation_ids=cancellation_ids_to_cancel,
            excluded_cancellation_ids=result.excluded_cancellation_ids,
            reason=normalized_reason,
            include_internal=include_internal,
            newly_cancelled_ids=newly_cancelled,
        )

    async def _await_scope_releases(
        self,
        *,
        reason: str,
        include_internal: bool,
        exclude_cancellation_ids: tuple[str, ...],
        timeout: float,
        targeted_ids: list[str],
        newly_cancelled_ids: list[str],
    ) -> None:
        deadline = time.monotonic() + timeout
        targeted_set = set(targeted_ids)
        newly_cancelled_set = set(newly_cancelled_ids)
        while True:
            active_scopes = await self._token_collection.get_all_scope_ids(
                include_internal=include_internal,
            )
            excluded_scopes = self._resolve_excluded_scopes(
                exclude_cancellation_ids=exclude_cancellation_ids,
                active_scopes=active_scopes,
            )
            pending_scopes = [
                scope_id for scope_id in active_scopes if scope_id not in excluded_scopes
            ]
            if not pending_scopes:
                return
            for scope_id in pending_scopes:
                if scope_id not in targeted_set:
                    targeted_set.add(scope_id)
                    targeted_ids.append(scope_id)
                if await self.cancel_scope(scope_id, reason):
                    if scope_id not in newly_cancelled_set:
                        newly_cancelled_set.add(scope_id)
                        newly_cancelled_ids.append(scope_id)
            remaining = deadline_remaining(deadline)
            if remaining <= 0:
                raise StateError(
                    "Cancellation scopes did not quiesce before the release deadline.",
                    details={"pending_cancellation_ids": pending_scopes},
                )
            await asyncio.sleep(min(remaining, SHORT_POLL_INTERVAL_SEC))

    @override
    async def clear_scope(self, cancellation_id: str) -> None:
        normalized_id = require_cancellation_id(cancellation_id)
        token_result = await self._token_collection.clear_scope(normalized_id)
        history_removed = await self._history.clear_scope(normalized_id)
        if token_result.scope_cleared or history_removed:
            await self._event_bus.publish_event("cancellation_cleared", normalized_id)

    @override
    async def reset_all(self) -> None:
        had_tokens = await self._token_collection.has_active_tokens(include_internal=True)
        had_history = await self._history.has_entries()
        await self._token_collection.clear_all()
        await self._history.clear_all()
        if had_tokens or had_history:
            await self._event_bus.publish_event("registry_reset")

    @override
    async def get_snapshot(self) -> JSONDict:
        scope_ids = await self._token_collection.get_all_scope_ids(include_internal=True)
        token_tasks = [
            self._token_collection.get_tokens_for_scope(scope_id) for scope_id in scope_ids
        ]
        scope_token_sets, history_snapshot = await asyncio.gather(
            asyncio.gather(*token_tasks, return_exceptions=False),
            self._history.get_snapshot(),
            return_exceptions=False,
        )
        tokens_copy = dict(zip(scope_ids, scope_token_sets, strict=False))
        return build_cancellation_snapshot(
            tokens_copy=tokens_copy,
            reasons_copy=history_snapshot.cancelled_reasons,
            order_copy=history_snapshot.cancelled_order,
        )

    @override
    async def sweep(self) -> SweepResult:
        sweep_result = await self._token_collection.sweep_cancelled()
        if sweep_result.removed_tokens or sweep_result.cleared_scopes:
            await self._event_bus.publish_event("registry_swept")
        return sweep_result
