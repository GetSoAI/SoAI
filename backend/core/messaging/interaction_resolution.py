"""SoAI - Durable Messaging interaction resolution contract [backend/core/messaging/interaction_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.types.json import JSONDict

__all__ = (
    "MessagingInteractionResolution",
    "MessagingInteractionTimeout",
)


@dataclass(frozen=True, slots=True)
class MessagingInteractionResolution:
    ingress_id: str
    route_id: str
    task_id: str
    conv_id: str
    user_id: int
    interaction_type: str
    checkpoint_generation: int
    payload: JSONDict = field(repr=False)


@dataclass(frozen=True, slots=True)
class MessagingInteractionTimeout:
    route_id: str
    task_id: str
    conv_id: str
    user_id: int
    interaction_type: str
    checkpoint_generation: int
