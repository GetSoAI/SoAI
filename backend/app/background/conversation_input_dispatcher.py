"""SoAI - Durable conversation input dispatcher [backend/app/background/conversation_input_dispatcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.background.conversation_input_worker import (
    run_conversation_input_worker,
)
from app.background.runtime_api_dependencies import (
    resolve_api_dependencies_from_runtime,
)
from core.di.validation import require_dependencies
from core.errors.exceptions import ServiceUnavailableError, StateError
from core.events.types_base import Event
from core.events.types_conversation_durable import (
    ConversationStreamCancellationRequestedEvent,
)
from core.events.types_system import ConversationInputsChangedEvent
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.runtime.soai_identifiers import build_soai_id, create_system_id
from core.tasks.progress import await_background_task_shutdown
from core.tasks.supervised_task_spawner import spawn_supervised_tracked_task
from features.api.routes.webui.conversation_input_queue_events import (
    publish_current_input_queue_changed,
)
from features.chat.conversation_stream_cancellation_operation import (
    CANCELLATION_REASON,
    accept_chat_stream_cancellation,
)

if TYPE_CHECKING:
    from core.events.protocols import DurableEventDeliveryProtocol, EventBusProtocol
    from core.runtime.protocols import RuntimeStateStoreProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("ConversationInputDispatcher", "ConversationInputDispatcherDependencies")

LOGGER_NAME = "SoAI.app.background.conversation_input_dispatcher"
DISPATCH_WORKER_COUNT = 4


@dataclass(frozen=True, slots=True)
class ConversationInputDispatcherDependencies:
    event_bus: EventBusProtocol
    durable_event_delivery: DurableEventDeliveryProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    runtime_state: RuntimeStateStoreProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ConversationInputDispatcherDependencies",
            event_bus=self.event_bus,
            durable_event_delivery=self.durable_event_delivery,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            runtime_state=self.runtime_state,
        )


class ConversationInputDispatcher:
    def __init__(self, deps: ConversationInputDispatcherDependencies) -> None:
        self._deps = deps
        self._logger = get_logger(LOGGER_NAME)
        self._shutdown_event = asyncio.Event()
        self._wake_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._subscribed = False
        self._server_boot_id = ""
        self._api_dependencies: ApiDependencies | None = None

    async def _handle_input_event(self, event: Event) -> None:
        if isinstance(event, ConversationInputsChangedEvent):
            self._wake_event.set()

    async def _handle_cancellation_event(self, event: Event) -> None:
        if not isinstance(event, ConversationStreamCancellationRequestedEvent):
            return
        api_dependencies = self._api_dependencies
        if api_dependencies is None:
            raise StateError("Chat stream cancellation recovery is not ready.")
        cancellation_id = create_system_id(
            subsystem="chat_stream_cancellation_recovery",
            owner=f"{event.user_id}:{event.conv_id}:{event.request_id}",
            include_random_suffix=False,
        )
        acceptance = await accept_chat_stream_cancellation(
            api_dependencies=api_dependencies,
            context=RequestContext(
                trace_id=cancellation_id,
                client_ip="internal",
                user_id=event.user_id,
                cancellation_id=cancellation_id,
            ),
            user_id=event.user_id,
            conv_id=event.conv_id,
            request_id=event.request_id,
            force_pending_steers=event.force_pending_steers,
            reason=CANCELLATION_REASON,
        )
        if acceptance.status == "cancellation_requested":
            raise ServiceUnavailableError("Accepted Chat stream cancellation is not terminal yet.")

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._shutdown_event = asyncio.Event()
        self._wake_event = asyncio.Event()
        self._server_boot_id = create_system_id(
            subsystem="conversation_input_dispatch",
            owner="server_boot",
            include_random_suffix=True,
        )
        if not self._subscribed:
            self._deps.event_bus.subscribe(
                ConversationInputsChangedEvent,
                self._handle_input_event,
            )
            self._deps.durable_event_delivery.subscribe(
                ConversationStreamCancellationRequestedEvent,
                self._handle_cancellation_event,
            )
            self._subscribed = True
        self._task = spawn_supervised_tracked_task(
            self._run,
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            cancellation_id=build_soai_id(("sys", "conversation_input", "dispatcher")),
            owner="conversation_input_dispatcher",
            name="conversation-input-dispatcher",
            logger=self._logger,
            metadata={"worker_count": DISPATCH_WORKER_COUNT},
        )

    async def _run(self) -> None:
        api_dependencies = await resolve_api_dependencies_from_runtime(self._deps.runtime_state)
        self._api_dependencies = api_dependencies
        recovered = (
            await api_dependencies.database_input_execution.reconcile_abandoned_input_claims()
        )
        for input_record in recovered:
            await self._publish_recovered_input(api_dependencies, input_record)
        async with asyncio.TaskGroup() as task_group:
            for worker_index in range(DISPATCH_WORKER_COUNT):
                _ = task_group.create_task(
                    run_conversation_input_worker(
                        api_dependencies,
                        worker_index=worker_index,
                        server_boot_id=self._server_boot_id,
                        shutdown_event=self._shutdown_event,
                        wake_event=self._wake_event,
                        logger=self._logger,
                    ),
                    name=f"conversation-input-worker-{worker_index}",
                )

    async def _publish_recovered_input(
        self,
        api_dependencies: ApiDependencies,
        input_record: JSONDict,
    ) -> None:
        conv_id = input_record.get("conv_id")
        user_id = input_record.get("user_id")
        if not isinstance(conv_id, str) or not isinstance(user_id, int):
            raise StateError("Recovered conversation input identity is invalid.")
        await publish_current_input_queue_changed(
            api_dependencies=api_dependencies,
            user_id=user_id,
            conv_id=conv_id,
        )

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        self._wake_event.set()
        await await_background_task_shutdown(
            self._task,
            logger=self._logger,
            operation="app.background.conversation_input_dispatcher.shutdown",
            message="Conversation input dispatcher failed during shutdown.",
            level="warning",
        )
        self._task = None
        self._api_dependencies = None
        if self._subscribed:
            self._deps.event_bus.unsubscribe(
                ConversationInputsChangedEvent,
                self._handle_input_event,
            )
            self._deps.durable_event_delivery.unsubscribe(
                ConversationStreamCancellationRequestedEvent,
                self._handle_cancellation_event,
            )
            self._subscribed = False
