"""SoAI - Prompt slot management with semaphore-based concurrency control [backend/orchestrator/queueing/priority/prompt_slots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace

from core.concurrency.swappable_resource import SwappableResource
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.orchestrator.protocols_queue import PromptSlotSnapshot
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task

__all__ = ("PromptSlotState",)

LOGGER_NAME = "SoAI.orchestrator.queueing.prompt_slots"
OPERATION_RECORD_GAUGE = "orchestrator.queueing.prompt_slots.record_gauge"


class PromptSlotState:
    def __init__(
        self,
        *,
        slot_limit: int,
        enabled: bool,
        metrics: MetricsManagerProtocol | None,
    ) -> None:
        self._metrics = metrics
        self._slot_limit = slot_limit
        self._slot_resource: SwappableResource[asyncio.Semaphore] = SwappableResource(
            asyncio.Semaphore(slot_limit),
        )
        self._slots_held = 0
        self._waiters = 0
        self._held_generation_by_tracking_id: dict[str, int] = {}
        self.enabled = enabled

    def _record_gauge(self, *keys: str, value: float) -> None:
        if self._metrics is None:
            return
        try:
            self._metrics.set_gauge(*keys, value=value)
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_RECORD_GAUGE,
            )
            log_exception(
                get_logger(LOGGER_NAME),
                coerced,
                message="Prompt-slot metric update failed.",
                operation=OPERATION_RECORD_GAUGE,
                details={"metric_path": ".".join(keys)},
                level="warning",
            )

    def snapshot(self) -> PromptSlotSnapshot:
        return {
            "enabled": bool(self.enabled),
            "limit": int(self._slot_limit),
            "held": int(self._slots_held),
            "waiters": int(self._waiters),
        }

    def update_mode(
        self,
        enabled: bool,
        *,
        slot_limit: int,
    ) -> None:
        previous_enabled = self.enabled
        previous_limit = self._slot_limit
        normalized = bool(enabled)
        self.enabled = normalized
        config_changed = previous_enabled != normalized or previous_limit != slot_limit
        if config_changed:
            old_semaphore = self._slot_resource.current
            waiter_count = self._waiters
            self._slot_limit = slot_limit
            available = max(0, slot_limit - self._slots_held) if self.enabled else 0
            self._slot_resource.swap(asyncio.Semaphore(available))
            self._record_gauge(
                "orchestrator",
                "prompt_queuing",
                "slots_held",
                value=self._slots_held,
            )
            self._record_gauge(
                "orchestrator",
                "prompt_queuing",
                "slot_limit",
                value=slot_limit,
            )
            if waiter_count > 0:
                for _ in range(waiter_count):
                    old_semaphore.release()

    async def acquire(
        self,
        task: Task,
        require_orchestration_context: Callable[[Task], OrchestrationContext],
    ) -> Task:
        context = require_orchestration_context(task)
        if context.prompt_slot_active:
            return task
        held_generation = self._held_generation_by_tracking_id.get(context.tracking_id)
        if held_generation is not None:
            context = replace(
                context,
                prompt_slot_active=True,
                prompt_slot_generation=held_generation,
            )
            return task.with_orchestration_context(context)
        if not self.enabled:
            return task
        while True:
            binding = self._slot_resource.bind()
            self._waiters += 1
            try:
                await binding.resource.acquire()
            finally:
                self._waiters = max(0, self._waiters - 1)
            if not self.enabled:
                binding.resource.release()
                return task
            if not self._slot_resource.is_current_generation(binding.generation):
                binding.resource.release()
                continue
            self._slots_held += 1
            self._held_generation_by_tracking_id[context.tracking_id] = binding.generation
            self._record_gauge(
                "orchestrator",
                "prompt_queuing",
                "slots_held",
                value=self._slots_held,
            )
            context = replace(
                context,
                prompt_slot_active=True,
                prompt_slot_generation=binding.generation,
            )
            return task.with_orchestration_context(context)

    def release(
        self,
        task: Task,
        require_orchestration_context: Callable[[Task], OrchestrationContext],
    ) -> Task:
        context: OrchestrationContext = require_orchestration_context(task)
        held_generation = self._held_generation_by_tracking_id.get(context.tracking_id)
        if not context.prompt_slot_active and held_generation is None:
            return task
        held_generation = self._held_generation_by_tracking_id.pop(context.tracking_id, None)
        context = replace(
            context,
            prompt_slot_active=False,
            prompt_slot_generation=None,
        )
        if held_generation is not None:
            self._slots_held = max(0, self._slots_held - 1)
            if self.enabled and self._slots_held < self._slot_limit:
                self._slot_resource.current.release()
        self._record_gauge(
            "orchestrator",
            "prompt_queuing",
            "slots_held",
            value=self._slots_held,
        )
        return task.with_orchestration_context(context)
