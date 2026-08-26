"""SoAI - Durable mutation claim execution [backend/app/background/mutation_command_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from app.background.mutation_claim_context import (
    build_mutation_claim_request_context,
)
from app.background.mutation_claim_lease import maintain_mutation_claim_lease
from app.background.mutation_command_decoding import decode_mutation_command
from app.background.mutation_publication_failures import (
    MUTATION_PUBLICATION_EXCEPTIONS,
    drain_mutation_reply_queue,
    finalize_failed_mutation_claim,
    log_mutation_publication_failure,
)
from app.background.mutation_recovery_signals import (
    mutation_command_is_storage_recovery,
    mutation_command_requested_recovery,
)
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.shutdown_waits import wait_for_shutdown_or_schedule_change
from core.concurrency.task_groups import cancel_and_await
from core.database.mutation_requests import MutationClaim
from core.database.protocols_tasks import DatabaseTasksProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.events.completion_signals import EventDispatchCompletion
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.mutations.edition_composition import DurableMutationComposition
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryProtocol
from core.timing.epoch import epoch_ms
from core.timing.retry_backoff import compute_exponential_backoff_seconds

__all__ = (
    "MutationCommandExecutionDependencies",
    "execute_mutation_claim",
)


@dataclass(frozen=True, slots=True)
class MutationCommandExecutionDependencies:
    database_tasks: DatabaseTasksProtocol
    database_plugins: DatabasePluginsProtocol
    event_bus: EventBusProtocol
    task_registry: TaskRegistryProtocol
    durable_mutations: DurableMutationComposition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MutationCommandExecutionDependencies",
            database_tasks=self.database_tasks,
            database_plugins=self.database_plugins,
            event_bus=self.event_bus,
            task_registry=self.task_registry,
            durable_mutations=self.durable_mutations,
        )


async def execute_mutation_claim(
    deps: MutationCommandExecutionDependencies,
    claim: MutationClaim,
    *,
    worker_id: str,
    lease_duration_ms: int,
    heartbeat_interval_sec: float,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    reply_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=1000)
    task = await deps.task_registry.attach_reply_queue(claim.task_id, reply_queue)
    if task is None:
        raise StateError("Accepted mutation task reply queue could not be attached.")
    if task.status.is_terminal():
        return
    if task.reply_queue is None:
        raise StateError("Accepted mutation task reply queue attachment was not retained.")
    reply_queue = task.reply_queue
    try:
        context = build_mutation_claim_request_context(claim, task)
    except StateError as exception:
        await finalize_failed_mutation_claim(
            deps.task_registry,
            request_id=claim.request_id,
            task_id=claim.task_id,
            fencing_token=claim.fencing_token,
            exception=exception,
            diagnostic_message="Accepted mutation authorization failed closed.",
            error_message="Accepted mutation authorization is invalid.",
            status_message="Mutation authorization failed closed.",
        )
        return
    claim_cancellation_id = context.cancellation_id
    try:
        command = decode_mutation_command(
            claim,
            context=context,
            reply_queue=reply_queue,
            fernets=deps.database_plugins.fernet,
            durable_mutations=deps.durable_mutations,
        )
    except StateError as exception:
        await finalize_failed_mutation_claim(
            deps.task_registry,
            request_id=claim.request_id,
            task_id=claim.task_id,
            fencing_token=claim.fencing_token,
            exception=exception,
            diagnostic_message="Accepted mutation recovery data failed closed.",
            error_message="Accepted mutation recovery data is invalid.",
            status_message="Mutation recovery failed closed.",
        )
        return
    drainer = asyncio.create_task(
        drain_mutation_reply_queue(reply_queue),
        name=f"mutation-reply-drainer-{claim.request_id}",
    )
    dispatch_completion: EventDispatchCompletion | None = None
    publish_failures = 0
    claim_lost_event = asyncio.Event()
    heartbeat_stopping_event = asyncio.Event()
    heartbeat: asyncio.Task[None] | None = None
    cancellation_dispatched = False
    try:
        renewed = await deps.database_tasks.renew_mutation_claim(
            claim.request_id,
            claim.fencing_token,
            worker_id,
            now_ms=epoch_ms(),
            lease_duration_ms=lease_duration_ms,
        )
        if not renewed:
            return
        heartbeat = asyncio.create_task(
            maintain_mutation_claim_lease(
                deps.database_tasks,
                claim,
                worker_id=worker_id,
                lease_duration_ms=lease_duration_ms,
                heartbeat_interval_sec=heartbeat_interval_sec,
                stopping_event=heartbeat_stopping_event,
                claim_lost_event=claim_lost_event,
            ),
            name=f"mutation-heartbeat-{claim.request_id}",
        )
        while not claim_lost_event.is_set() and (
            shutdown_event is None or not shutdown_event.is_set()
        ):
            if mutation_command_requested_recovery(command, deps.durable_mutations):
                return
            current_task = await deps.task_registry.get(claim.task_id, force_refresh=True)
            if current_task is None:
                raise StateError("Accepted mutation task disappeared during execution.")
            if current_task.status.is_terminal():
                return
            storage_recovery = mutation_command_is_storage_recovery(
                command,
                claim.attempt_count,
                deps.durable_mutations,
            )
            if current_task.cancellation_requested_at_ms is not None and not storage_recovery:
                if dispatch_completion is None:
                    await finalize(
                        deps.task_registry,
                        claim.task_id,
                        TaskStatus.CANCELLED,
                        error_message="Mutation cancellation requested.",
                        status_message="Mutation cancelled before execution.",
                        mutation_fencing_token=claim.fencing_token,
                    )
                    return
                if not cancellation_dispatched:
                    await deps.task_registry.cancellation_coordinator.cancel_scope(
                        claim_cancellation_id,
                        "Mutation cancellation requested.",
                    )
                    cancellation_dispatched = True
                    await asyncio.sleep(heartbeat_interval_sec)
                    continue
            if dispatch_completion is None:
                dispatch_completion = EventDispatchCompletion()
                try:
                    await deps.event_bus.publish(
                        command,
                        wait_for_completion=dispatch_completion,
                    )
                except MUTATION_PUBLICATION_EXCEPTIONS as exception:
                    publication = dispatch_completion.snapshot()
                    if not publication.was_enqueued:
                        dispatch_completion = None
                    publish_failures += 1
                    if publish_failures == 1 or publish_failures & (publish_failures - 1) == 0:
                        log_mutation_publication_failure(
                            exception,
                            attempt=publish_failures,
                            task_id=claim.task_id,
                            was_enqueued=publication.was_enqueued,
                        )
            elif dispatch_completion.is_set():
                completion = dispatch_completion.snapshot()
                if completion.succeeded:
                    await asyncio.sleep(heartbeat_interval_sec)
                    continue
                completed_task = await deps.task_registry.get(
                    claim.task_id,
                    force_refresh=True,
                )
                if completed_task is None:
                    raise StateError("Accepted mutation task disappeared after dispatch.")
                if completed_task.status.is_terminal():
                    return
                detail = completion.failure_message or (
                    "Mutation command handler exited without terminalizing its accepted task."
                )
                await finalize_failed_mutation_claim(
                    deps.task_registry,
                    request_id=claim.request_id,
                    task_id=claim.task_id,
                    fencing_token=claim.fencing_token,
                    exception=StateError(detail),
                    diagnostic_message="Accepted mutation command failed closed after dispatch.",
                    error_message="Accepted mutation command did not complete safely.",
                    status_message="Mutation execution failed closed.",
                )
                return
            retry_delay = heartbeat_interval_sec
            if dispatch_completion is None and publish_failures:
                retry_delay = compute_exponential_backoff_seconds(
                    publish_failures - 1,
                    base_seconds=heartbeat_interval_sec,
                    maximum_seconds=30.0,
                    jitter_ratio=0.2,
                )
            if shutdown_event is None:
                await asyncio.sleep(retry_delay)
            elif (
                await wait_for_shutdown_or_schedule_change(
                    shutdown_event,
                    None,
                    retry_delay,
                )
                == "shutdown"
            ):
                break
    finally:
        heartbeat_stopping_event.set()
        if dispatch_completion is not None and not dispatch_completion.is_set():
            await uncancel_then_cleanup(
                deps.task_registry.cancellation_coordinator.cancel_scope(
                    claim_cancellation_id,
                    "Durable mutation claim ownership was lost.",
                )
            )
        await cancel_and_await(
            (heartbeat, drainer),
            task_label="durable mutation claim support tasks",
        )
        if (
            sys.exception() is None
            and heartbeat is not None
            and heartbeat.done()
            and not heartbeat.cancelled()
        ):
            heartbeat.result()
