"""SoAI - Task state merge policy for cached and incoming tasks [backend/core/tasks/task_state_merge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import dataclasses

from core.errors.exceptions import ValidationError
from core.tasks.task import Task

__all__ = ("merge_task_state",)


def merge_task_state(*, cached: Task | None, incoming: Task) -> Task:
    if cached is None:
        return incoming
    if cached.task_id != incoming.task_id:
        raise ValidationError("Cannot merge tasks with different task_id values.")
    cached_terminal = cached.status.is_terminal()
    incoming_terminal = incoming.status.is_terminal()
    if cached_terminal and (not incoming_terminal):
        cached_context = cached.orchestration_context
        cached_event = cached_context.event if cached_context is not None else None
        if incoming.update_counter > cached.update_counter and cached_event is None:
            return _apply_non_persisted_fields(base=incoming, cached=cached)
        return cached
    cached_key = (int(cached.updated_at_ms), int(cached.update_counter))
    incoming_key = (int(incoming.updated_at_ms), int(incoming.update_counter))
    if incoming_key > cached_key:
        return _apply_non_persisted_fields(base=incoming, cached=cached)
    if incoming_key < cached_key:
        return cached
    if incoming_terminal and (not cached_terminal):
        return _apply_non_persisted_fields(base=incoming, cached=cached)
    return cached


def _apply_non_persisted_fields(*, base: Task, cached: Task) -> Task:
    reply_queue = base.reply_queue if base.reply_queue is not None else cached.reply_queue
    base_context = base.orchestration_context
    cached_context = cached.orchestration_context
    orchestration_context = base_context if base_context is not None else cached_context
    if base_context is not None and cached_context is not None:
        base_event = base_context.event
        cached_event = cached_context.event
        if base_event is None and cached_event is not None:
            orchestration_context = dataclasses.replace(base_context, event=cached_event)
    return dataclasses.replace(
        base,
        reply_queue=reply_queue,
        orchestration_context=orchestration_context,
    )
