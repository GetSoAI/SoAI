"""SoAI - Event base types [backend/core/events/types_base.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

from core.events.id_generation import generate_event_id

if TYPE_CHECKING:
    from core.types.json import JSONDict

    type ReplyChannel = asyncio.Queue["Event"]

__all__ = (
    "BaseCommand",
    "Event",
    "EventDelivery",
    "PayloadEvent",
    "ReplyableCommand",
    "ReplyableUserCommand",
    "UserCommand",
)


class EventDelivery(Enum):
    MUST_DELIVER = "must_deliver"
    DROPPABLE = "droppable"


@dataclass(kw_only=True, slots=True)
class Event:
    TIMEOUT: ClassVar[float | None] = None
    trace_id: str | None = None
    event_id: str = field(default_factory=generate_event_id)
    timestamp: float = field(default_factory=time.time)


@dataclass(kw_only=True, slots=True)
class PayloadEvent(Event):
    payload: JSONDict


@dataclass(kw_only=True, slots=True)
class BaseCommand(Event): ...


@dataclass(kw_only=True, slots=True)
class UserCommand(BaseCommand): ...


@dataclass(kw_only=True, slots=True)
class ReplyableCommand(BaseCommand):
    reply_channel: asyncio.Queue[Event]
    delivery: EventDelivery = EventDelivery.MUST_DELIVER


@dataclass(kw_only=True, slots=True)
class ReplyableUserCommand(ReplyableCommand, UserCommand): ...
