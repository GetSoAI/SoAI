"""SoAI - Parameter update/delete queue submission [backend/models/parameters/mutation/update_queue_submission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from models.parameters.mutation.types import DeleteTaskPayload, UpdateTaskPayload

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.types.json import JSONDict
    from models.parameters.mutation.types import UpdateQueuePayload
    from models.parameters.mutation_ordering import MutationOrderTracker

__all__ = (
    "enqueue_parameter_delete",
    "enqueue_parameter_update",
)


async def enqueue_parameter_update(
    *,
    update_queue: asyncio.Queue[tuple[str, UpdateQueuePayload] | None],
    order_tracker: MutationOrderTracker,
    universal_id: str,
    parameters: JSONDict,
    reply_channel: asyncio.Queue[Event],
) -> None:
    order = order_tracker.next_universal_id_order(universal_id)
    order_tracker.register_expected_order(universal_id, order)
    payload: UpdateTaskPayload = {
        "universal_id": universal_id,
        "parameters": parameters,
        "reply_channel": reply_channel,
        "order": order,
    }
    try:
        await asyncio.wait_for(
            update_queue.put(("update", payload)), timeout=RESPONSIVE_TIMEOUT_SEC
        )
    except (TimeoutError, asyncio.CancelledError):
        order_tracker.revoke_expected_order(universal_id, order)
        raise


async def enqueue_parameter_delete(
    *,
    update_queue: asyncio.Queue[tuple[str, UpdateQueuePayload] | None],
    order_tracker: MutationOrderTracker,
    universal_id: str,
    keys: list[str],
    reply_channel: asyncio.Queue[Event],
) -> None:
    order = order_tracker.next_universal_id_order(universal_id)
    order_tracker.register_expected_order(universal_id, order)
    payload: DeleteTaskPayload = {
        "universal_id": universal_id,
        "keys": keys,
        "reply_channel": reply_channel,
        "order": order,
    }
    try:
        await asyncio.wait_for(
            update_queue.put(("delete", payload)), timeout=RESPONSIVE_TIMEOUT_SEC
        )
    except (TimeoutError, asyncio.CancelledError):
        order_tracker.revoke_expected_order(universal_id, order)
        raise
