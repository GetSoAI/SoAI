"""SoAI - Task cancellation binding workflow [backend/core/tasks/task_cancellation_binder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.concurrency.cancellation import CancellationToken, make_task_cancel_callback
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.tasks.cancellation_ids import require_cancellation_id
from core.tasks.cancellation_token_release import release_cancellation_token
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TokenCollectionProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "TaskCancellationBinder",
    "TaskCancellationBinderDependencies",
)


@dataclass(frozen=True, slots=True)
class TaskCancellationBinderDependencies:
    token_collection: TokenCollectionProtocol
    history: CancellationHistoryProtocol
    event_bus: CancellationEventBusProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TaskCancellationBinderDependencies",
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
            history=self.history,
            token_collection=self.token_collection,
        )


class TaskCancellationBinder(TaskCancellationBinderProtocol):
    __slots__ = (
        "_binding_lock",
        "_bindings",
        "_event_bus",
        "_finalizer_tracker",
        "_history",
        "_token_collection",
    )

    def __init__(self, deps: TaskCancellationBinderDependencies) -> None:
        self._token_collection = deps.token_collection
        self._history = deps.history
        self._event_bus = deps.event_bus
        self._finalizer_tracker = deps.finalizer_tracker
        self._binding_lock = asyncio.Lock()
        self._bindings: dict[tuple[int, str], CancellationToken] = {}

    @override
    async def bind_task[TaskResult](
        self,
        cancellation_id: str,
        task: asyncio.Task[TaskResult],
        *,
        owner: str,
        metadata: dict[str, JSONValue] | None = None,
    ) -> CancellationToken:
        binding_loop = asyncio.get_running_loop()
        task_loop = task.get_loop()
        normalized_id = require_cancellation_id(cancellation_id)
        binding_key = (id(task), normalized_id)
        async with self._binding_lock:
            existing_token = self._bindings.get(binding_key)
            if existing_token is not None:
                return existing_token
            cancel_callback = make_task_cancel_callback(task_loop, task, normalized_id, owner)
            token = CancellationToken(
                normalized_id,
                owner=owner,
                metadata=metadata,
                on_cancel=cancel_callback,
            )
            token_added = False
            registration_event_published = False
            try:
                add_result = await self._token_collection.add_token(normalized_id, token)
                token_added = add_result.added
                if not add_result.added:
                    raise StateError("Task cancellation token registration was rejected.")
                await self._event_bus.publish_event("token_registered", normalized_id)
                registration_event_published = True
                existing_reason = await self._history.get_reason(normalized_id)
                if existing_reason:
                    token.cancel(existing_reason)

                def _schedule_release() -> None:
                    if binding_loop.is_closed():
                        return
                    try:
                        release_task = create_ephemeral_task(
                            self._release_binding(binding_key, token, normalized_id),
                            name=f"release-token:{normalized_id}",
                            log_exceptions=False,
                        )
                    except RuntimeError:
                        if binding_loop.is_closed():
                            return
                        raise
                    self._finalizer_tracker.track_finalizer(release_task)

                def _on_task_done(_completed: asyncio.Task[TaskResult]) -> None:
                    if binding_loop.is_closed():
                        return
                    running_loop: asyncio.AbstractEventLoop | None
                    try:
                        running_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        running_loop = None
                    if running_loop is binding_loop:
                        _schedule_release()
                        return
                    try:
                        binding_loop.call_soon_threadsafe(_schedule_release)
                    except RuntimeError:
                        return

                self._bindings[binding_key] = token
                task.add_done_callback(_on_task_done)
            except asyncio.CancelledError as exception:
                if token_added:
                    await self._release_token_after_setup_failure(
                        token,
                        normalized_id,
                        registration_event_published,
                        exception,
                    )
                raise
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                if token_added:
                    await self._release_token_after_setup_failure(
                        token,
                        normalized_id,
                        registration_event_published,
                        exception,
                    )
                raise
        return token

    async def _release_binding(
        self,
        binding_key: tuple[int, str],
        token: CancellationToken,
        cancellation_id: str,
    ) -> None:
        await self._release_token(token, cancellation_id)
        async with self._binding_lock:
            self._bindings.pop(binding_key, None)

    async def _release_token(self, token: CancellationToken, cancellation_id: str) -> None:
        await release_cancellation_token(
            token_collection=self._token_collection,
            cancellation_history=self._history,
            cancellation_event_bus=self._event_bus,
            cancellation_id=cancellation_id,
            token=token,
            publish_release_event=True,
        )

    async def _release_token_after_setup_failure(
        self,
        token: CancellationToken,
        cancellation_id: str,
        publish_release_event: bool,
        primary_exception: BaseException,
    ) -> None:
        try:
            await uncancel_then_cleanup(
                release_cancellation_token(
                    token_collection=self._token_collection,
                    cancellation_history=self._history,
                    cancellation_event_bus=self._event_bus,
                    cancellation_id=cancellation_id,
                    token=token,
                    publish_release_event=publish_release_event,
                ),
            )
        except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
            primary_exception.add_note(
                f"Cancellation token setup cleanup failed: {cleanup_exception}",
            )
