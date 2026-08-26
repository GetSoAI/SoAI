"""SoAI - Shared mutation side effects for model catalog changes [backend/models/mutation_notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.events.protocols import EventBusProtocol
from core.events.types_models_model_events import ModelDatabaseChangeEvent

__all__ = ("notify_model_catalog_changed",)


async def notify_model_catalog_changed(
    *,
    model_invalidate_list_caches: Callable[[], Awaitable[None]],
    event_bus: EventBusProtocol,
    added_universal_ids: list[str] | None = None,
    removed_universal_ids: list[str] | None = None,
) -> None:
    await model_invalidate_list_caches()
    event = ModelDatabaseChangeEvent(
        added_universal_ids=list(added_universal_ids or []),
        removed_universal_ids=list(removed_universal_ids or []),
    )
    await event_bus.publish(event)
