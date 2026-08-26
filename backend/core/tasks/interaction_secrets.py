"""SoAI - Claimed task interaction secret contracts [backend/core/tasks/interaction_secrets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.errors.exceptions import StateError
from core.timing.durations import minutes_to_ms
from core.web.site_scope import SiteScope

__all__ = (
    "ClaimedInteractionSecret",
    "InteractionSecretClaimIdentity",
    "InteractionSecretEffectUnknownError",
    "interaction_secret_handoff_ttl_ms",
)


def interaction_secret_handoff_ttl_ms() -> int:
    return minutes_to_ms(10)


class InteractionSecretEffectUnknownError(StateError): ...


@dataclass(frozen=True, slots=True)
class InteractionSecretClaimIdentity:
    task_id: str
    claim_generation: int
    claim_owner: str


@dataclass(frozen=True, slots=True)
class ClaimedInteractionSecret:
    identity: InteractionSecretClaimIdentity
    user_id: int
    conv_id: str
    scope: SiteScope
    username: str | None
    password: str = field(repr=False)
