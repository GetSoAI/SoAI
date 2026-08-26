"""SoAI - Core rate limiting definitions [backend/core/rate_limiting/definitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "RateLimitDecision",
    "RateLimitRule",
    "RateLimitWindowStats",
)


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    amount: int
    window_seconds: int
    label: str

    @property
    def storage_key(self) -> str:
        return f"{self.amount}:{self.window_seconds}"


@dataclass(frozen=True, slots=True)
class RateLimitWindowStats:
    limit: int
    remaining: int
    reset_epoch_seconds: int


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    failed_rule: RateLimitRule | None
    stats: RateLimitWindowStats | None
