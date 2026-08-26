"""SoAI - Parameter mutation queue payload and item types [backend/models/parameters/mutation/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, TypedDict

from core.events.types_base import Event

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from models.parameters.mutation_ordering import MutationCallable

    type UpdateQueuePayload = UpdateTaskPayload | DeleteTaskPayload
    type MutationQueueItem = tuple[
        tuple[int, int],
        bool,
        str,
        int | None,
        MutationCallable,
        asyncio.Future[None],
    ]
else:
    UpdateQueuePayload = dict
    MutationQueueItem = tuple

__all__ = (
    "DeleteTaskPayload",
    "UpdateTaskPayload",
)


class UpdateTaskPayload(TypedDict):
    universal_id: str
    parameters: JSONDict
    reply_channel: asyncio.Queue[Event]
    order: int


class DeleteTaskPayload(TypedDict):
    universal_id: str
    keys: list[str]
    reply_channel: asyncio.Queue[Event]
    order: int
