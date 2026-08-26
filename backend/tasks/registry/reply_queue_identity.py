"""SoAI - Task registry reply queue identity bindings [backend/tasks/registry/reply_queue_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import weakref

from core.errors.exceptions import ValidationError
from core.events.types_base import Event

__all__ = ("ReplyQueueIdentityBindings",)


class ReplyQueueIdentityBindings:

    def __init__(self) -> None:
        self._bindings: weakref.WeakKeyDictionary[asyncio.Queue[Event], tuple[str, int]]
        self._bindings = weakref.WeakKeyDictionary()

    def bind(self, reply_queue: asyncio.Queue[Event], *, task_id: str, user_id: int) -> None:
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            raise ValidationError("task_id must be a non-empty string.")
        if reply_queue is None:
            raise ValidationError("reply_queue is required.")
        self._bindings[reply_queue] = (normalized_task_id, int(user_id))

    def resolve(self, reply_queue: asyncio.Queue[Event]) -> tuple[str, int] | None:
        identity = self._bindings.get(reply_queue)
        if identity is None:
            return None
        task_id, user_id = identity
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return None
        return (normalized_task_id, int(user_id))
