"""SoAI - WebUI session invalidation publication [backend/features/api/routes/webui/session_invalidation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exceptions import StateError
from core.events.completion_signals import EventDispatchCompletion
from core.events.protocols import EventBusProtocol
from core.events.types_webui import UserSessionInvalidatedEvent
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = ("publish_user_session_invalidation",)


async def publish_user_session_invalidation(
    event_bus: EventBusProtocol,
    *,
    user_id: int,
    username: str,
    reason: str,
    session_jtis: tuple[str, ...] | None = None,
) -> None:
    completion = EventDispatchCompletion()
    await event_bus.publish(
        UserSessionInvalidatedEvent(
            user_id=user_id,
            username=username,
            reason=reason,
            session_jtis=session_jtis,
        ),
        wait_for_completion=completion,
    )
    try:
        await asyncio.wait_for(completion.wait(), timeout=CONTROL_TIMEOUT_SEC)
    except TimeoutError as exception:
        raise StateError("Timed out while invalidating active WebUI sessions.") from exception
    if not completion.snapshot().succeeded:
        raise StateError("Failed to invalidate active WebUI sessions.")
