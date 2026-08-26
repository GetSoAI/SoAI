"""SoAI - Runtime state for API request rate limiting [backend/features/api/rate_limiting/runtime_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.rate_limiting.definitions import RateLimitRule, RateLimitWindowStats
from core.rate_limiting.moving_window import MovingWindowRateLimiter
from features.api.rate_limiting.rate_limit_resolution import ResolvedRateLimitConfig

if TYPE_CHECKING:
    from starlette.datastructures import State

__all__ = (
    "RateLimitRuntimeHit",
    "RateLimitRuntimeState",
    "ensure_rate_limit_runtime_state",
    "get_rate_limit_runtime_state",
    "get_request_rate_limit_runtime_state",
)


@dataclass(frozen=True, slots=True)
class RateLimitRuntimeHit:
    rule: RateLimitRule
    scope_key: str
    stats: RateLimitWindowStats


class RateLimitRuntimeState:
    def __init__(self, request_rate_limiter: MovingWindowRateLimiter) -> None:
        self._lock = threading.RLock()
        self._request_rate_limiter = request_rate_limiter
        self._resolved_config: ResolvedRateLimitConfig | None = None

    def get_config(self) -> ResolvedRateLimitConfig | None:
        with self._lock:
            return self._resolved_config

    def owns_limiter(self, request_rate_limiter: MovingWindowRateLimiter) -> bool:
        with self._lock:
            return self._request_rate_limiter is request_rate_limiter

    def replace_config(
        self,
        config: ResolvedRateLimitConfig | None,
        *,
        reset_counters: bool,
    ) -> None:
        with self._lock:
            if reset_counters:
                self._request_rate_limiter.reset()
            self._resolved_config = config

    def hit(
        self,
        *,
        route_path: str | None,
        route_path_format: str | None,
        client_key: str,
    ) -> RateLimitRuntimeHit | None:
        with self._lock:
            config = self._resolved_config
            if not isinstance(config, ResolvedRateLimitConfig) or not config.enabled:
                return None
            resolved = config.path_limits.get(route_path) if route_path else None
            if resolved is None and route_path_format:
                resolved = config.path_limits.get(route_path_format)
            if resolved is None:
                return None
            scope_key = route_path_format or route_path or ""
            decision = self._request_rate_limiter.hit(
                rules=resolved.rules,
                client_key=client_key,
                scope_key=scope_key,
            )
            if decision.allowed:
                return None
            if decision.failed_rule is None or decision.stats is None:
                raise StateError("Rate limiter returned an invalid denial decision.")
            return RateLimitRuntimeHit(
                rule=decision.failed_rule,
                scope_key=scope_key,
                stats=decision.stats,
            )


def get_rate_limit_runtime_state(app_state: State) -> RateLimitRuntimeState | None:
    try:
        runtime = app_state.rate_limit_runtime
    except AttributeError:
        return None
    if not isinstance(runtime, RateLimitRuntimeState):
        raise StateError("rate_limit_runtime is invalid.")
    return runtime


def get_request_rate_limit_runtime_state(app_state: State) -> RateLimitRuntimeState | None:
    runtime = get_rate_limit_runtime_state(app_state)
    if runtime is not None:
        return runtime
    try:
        request_rate_limiter = app_state.request_rate_limiter
    except AttributeError:
        return None
    if not isinstance(request_rate_limiter, MovingWindowRateLimiter):
        raise StateError("request_rate_limiter is invalid.")
    raise StateError("rate_limit_runtime is not configured.")


def ensure_rate_limit_runtime_state(
    app_state: State,
    request_rate_limiter: MovingWindowRateLimiter,
) -> RateLimitRuntimeState:
    runtime = get_rate_limit_runtime_state(app_state)
    if runtime is not None:
        if not runtime.owns_limiter(request_rate_limiter):
            raise StateError("Rate limit runtime is bound to a different limiter.")
        return runtime
    runtime = RateLimitRuntimeState(request_rate_limiter)
    app_state.rate_limit_runtime = runtime
    return runtime
