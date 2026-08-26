"""SoAI - Routing config command types [backend/core/events/types_models_routing_commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.events.types_base import ReplyableUserCommand
from core.runtime.request_context import RequestContext

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "GetRoutingConfigCommand",
    "UpdateRoutingConfigCommand",
)


@dataclass(slots=True)
class GetRoutingConfigCommand(ReplyableUserCommand):
    context: RequestContext | None = None


@dataclass(slots=True)
class UpdateRoutingConfigCommand(ReplyableUserCommand):
    action: Literal["add", "remove", "set_enabled", "update"]
    entity_type: str
    data: JSONDict
    context: RequestContext | None = None
