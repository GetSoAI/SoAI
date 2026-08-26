"""SoAI - AI Horde anonymous request rate gate [backend/mcp/tools/generate_image_horde_rate_limit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from core.rate_limiting.definitions import RateLimitDecision, RateLimitRule
from core.rate_limiting.moving_window import MovingWindowRateLimiter
from mcp.tools.generate_image_horde_constants import (
    ANONYMOUS_HORDE_API_KEY,
    ANONYMOUS_HORDE_BASE_URL,
)

__all__ = ("AnonymousHordeRateGate",)

_ANONYMOUS_SCOPE_KEY = "generate_image:ai_horde:anonymous"
_ANONYMOUS_CLIENT_IDENTIFIER = "stablehorde.net"
_ANONYMOUS_RATE_AMOUNT = 9
_ANONYMOUS_RATE_WINDOW_SECONDS = 60
_ANONYMOUS_RATE_LABEL = "9 per 1 minute"
_MAX_WAIT_SECONDS = 65.0


@dataclass(slots=True)
class AnonymousHordeRateGate:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    limiter: MovingWindowRateLimiter = field(default_factory=MovingWindowRateLimiter)
    rule: RateLimitRule = field(
        default_factory=lambda: RateLimitRule(
            amount=_ANONYMOUS_RATE_AMOUNT,
            window_seconds=_ANONYMOUS_RATE_WINDOW_SECONDS,
            label=_ANONYMOUS_RATE_LABEL,
        ),
    )

    async def reserve(self, *, base_url: str, api_key: str, deadline_monotonic: float) -> bool:
        if base_url != ANONYMOUS_HORDE_BASE_URL or api_key != ANONYMOUS_HORDE_API_KEY:
            return True
        while True:
            async with self.lock:
                decision = self.limiter.hit(
                    rules=(self.rule,),
                    client_key=_ANONYMOUS_CLIENT_IDENTIFIER,
                    scope_key=_ANONYMOUS_SCOPE_KEY,
                )
                if decision.allowed:
                    return True
                wait_seconds = _resolve_decision_wait_seconds(decision)
            if time.monotonic() + wait_seconds >= deadline_monotonic:
                return False
            await asyncio.sleep(wait_seconds)


def _resolve_decision_wait_seconds(decision: RateLimitDecision) -> float:
    stats = decision.stats
    if stats is None:
        return 1.0
    return max(1.0, min(_MAX_WAIT_SECONDS, float(stats.reset_epoch_seconds) - time.time() + 1.0))
