"""SoAI - Active cancellation token collection management [backend/core/tasks/token_collection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.concurrency.protocols import CancellationTokenProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.tasks.cancellation_ids import (
    is_system_cancellation_id,
    normalize_cancellation_id,
    require_cancellation_id,
)
from core.tasks.cancellation_types import (
    AddTokenResult,
    ClearScopeResult,
    RemoveTokenResult,
    SweepResult,
)

__all__ = (
    "TokenCollection",
    "TokenCollectionDependencies",
)


@dataclass(frozen=True, slots=True)
class TokenCollectionDependencies:
    def __post_init__(self) -> None:
        require_dependencies(owner="TokenCollectionDependencies")


class TokenCollection:
    __slots__ = ("_lock", "_tokens_by_id")

    def __init__(self, _dependencies: TokenCollectionDependencies) -> None:
        self._tokens_by_id: dict[str, set[CancellationTokenProtocol]] = {}
        self._lock = asyncio.Lock()

    async def add_token(
        self,
        cancellation_id: str,
        token: CancellationTokenProtocol,
    ) -> AddTokenResult:
        normalized_id = require_cancellation_id(cancellation_id)
        try:
            token_cancellation_id = token.cancellation_id
        except AttributeError:
            token_cancellation_id = ""
        token_id = normalize_cancellation_id(token_cancellation_id)
        if token_id != normalized_id:
            raise ValidationError("Cancellation token id must match the target cancellation_id.")
        async with self._lock:
            token_set = self._tokens_by_id.get(normalized_id)
            if token_set is None:
                token_set = set[CancellationTokenProtocol]()
                self._tokens_by_id[normalized_id] = token_set
            previous_size = len(token_set)
            token_set.add(token)
            added = len(token_set) != previous_size
        return AddTokenResult(added=added, scope_id=normalized_id)

    async def remove_token(
        self,
        cancellation_id: str,
        token: CancellationTokenProtocol,
    ) -> RemoveTokenResult:
        normalized_id = normalize_cancellation_id(cancellation_id)
        if not normalized_id:
            return RemoveTokenResult(removed=False, scope_cleared=False, remaining_tokens=0)
        removed = False
        scope_cleared = False
        remaining_tokens = 0
        async with self._lock:
            token_set = self._tokens_by_id.get(normalized_id)
            if token_set is not None:
                matching_token = next(
                    (candidate for candidate in token_set if candidate is token),
                    None,
                )
                if matching_token is not None:
                    token_set.discard(matching_token)
                    removed = True
                remaining_tokens = len(token_set)
                if not token_set:
                    self._tokens_by_id.pop(normalized_id, None)
                    scope_cleared = True
        return RemoveTokenResult(
            removed=removed,
            scope_cleared=scope_cleared,
            remaining_tokens=remaining_tokens,
        )

    async def get_tokens_for_scope(self, cancellation_id: str) -> set[CancellationTokenProtocol]:
        normalized_id = normalize_cancellation_id(cancellation_id)
        if not normalized_id:
            return set()
        async with self._lock:
            tokens = self._tokens_by_id.get(normalized_id, set())
            return set[CancellationTokenProtocol](tokens)

    async def get_all_scope_ids(self, *, include_internal: bool) -> list[str]:
        async with self._lock:
            scope_ids = [
                scope_id
                for scope_id, tokens in self._tokens_by_id.items()
                if tokens and (include_internal or not is_system_cancellation_id(scope_id))
            ]
        scope_ids.sort()
        return scope_ids

    async def has_active_tokens(self, *, include_internal: bool) -> bool:
        async with self._lock:
            return any(
                tokens
                for scope_id, tokens in self._tokens_by_id.items()
                if tokens and (include_internal or not is_system_cancellation_id(scope_id))
            )

    async def sweep_cancelled(self) -> SweepResult:
        removed_tokens = 0
        cleared_scopes = 0
        async with self._lock:
            pruned: dict[str, set[CancellationTokenProtocol]] = {}
            for scope_id, token_set in self._tokens_by_id.items():
                if not token_set:
                    continue
                remaining_tokens = {token for token in token_set if not token.thread_event.is_set()}
                removed_tokens += len(token_set) - len(remaining_tokens)
                if remaining_tokens:
                    pruned[scope_id] = remaining_tokens
                else:
                    cleared_scopes += 1
            self._tokens_by_id = pruned
            remaining_scopes = len(self._tokens_by_id)
        return SweepResult(
            removed_tokens=removed_tokens,
            cleared_scopes=cleared_scopes,
            remaining_scopes=remaining_scopes,
        )

    async def clear_scope(self, cancellation_id: str) -> ClearScopeResult:
        normalized_id = require_cancellation_id(cancellation_id)
        async with self._lock:
            token_set = self._tokens_by_id.pop(normalized_id, None)
        removed_tokens = len(token_set) if token_set else 0
        return ClearScopeResult(
            removed_tokens=removed_tokens,
            scope_cleared=token_set is not None,
        )

    async def clear_all(self) -> None:
        async with self._lock:
            self._tokens_by_id.clear()
