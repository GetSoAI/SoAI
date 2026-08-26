"""SoAI - Shared rate limit evaluation for HTTP and WebSocket API routes [backend/features/api/rate_limiting/rate_limit_evaluator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.rate_limiting.definitions import RateLimitRule, RateLimitWindowStats
from core.runtime.protocols import RequestProtocol
from features.api.rate_limiting.runtime_state import (
    get_request_rate_limit_runtime_state,
)
from features.api.runtime.context import get_remote_address

__all__ = (
    "ApiRateLimitExceeded",
    "RateLimitBreach",
    "evaluate_rate_limit",
)


@dataclass(frozen=True, slots=True)
class RateLimitBreach:
    rule: RateLimitRule
    client_key: str
    scope_key: str
    stats: RateLimitWindowStats


class ApiRateLimitExceeded(Exception):
    def __init__(self, breach: RateLimitBreach) -> None:
        self.breach = breach
        super().__init__("Rate limit exceeded.")


async def evaluate_rate_limit(
    connection: RequestProtocol,
    route_path: str | None,
    route_path_format: str | None,
) -> RateLimitBreach | None:
    client_key = get_remote_address(connection)
    runtime_state = get_request_rate_limit_runtime_state(connection.app.state)
    if runtime_state is None:
        return None
    hit = runtime_state.hit(
        route_path=route_path,
        route_path_format=route_path_format,
        client_key=client_key,
    )
    if hit is None:
        return None
    return RateLimitBreach(
        rule=hit.rule,
        client_key=client_key,
        scope_key=hit.scope_key,
        stats=hit.stats,
    )
