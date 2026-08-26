"""SoAI - API authentication rate-limit warning tracking [backend/features/api/middleware/authentication_rate_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Request, status

from core.logging.trace import get_logger

__all__ = (
    "RateLimitWarningState",
    "get_rate_limit_warning_state",
    "log_rate_limit_warning",
)

LOGGER_NAME = "SoAI.features.api.authentication_rate_limits"


_RATE_LIMIT_WARNING_THROTTLE_SECONDS = 20.0
_RATE_LIMIT_MAX_TRACKED_KEYS = 1024
_RATE_LIMIT_EVICTION_TTL_SECONDS = 300.0


@lru_cache(maxsize=1)
def _state_init_lock_cached() -> threading.Lock:
    return threading.Lock()


def _get_state_init_lock() -> threading.Lock:
    return _state_init_lock_cached()


@dataclass(slots=True)
class RateLimitWarningState:
    lock: threading.Lock
    last_logged_by_key: OrderedDict[str, float]
    suppressed_by_key: OrderedDict[str, int]


def _evict_stale_rate_limit_entries(
    state: RateLimitWarningState,
    current_time: float,
) -> None:
    stale_threshold = current_time - _RATE_LIMIT_EVICTION_TTL_SECONDS
    while state.last_logged_by_key:
        oldest_key = next(iter(state.last_logged_by_key))
        oldest_time = state.last_logged_by_key[oldest_key]
        if oldest_time >= stale_threshold:
            break
        del state.last_logged_by_key[oldest_key]
        state.suppressed_by_key.pop(oldest_key, None)
    while len(state.last_logged_by_key) > _RATE_LIMIT_MAX_TRACKED_KEYS:
        evicted_key, _ = state.last_logged_by_key.popitem(last=False)
        state.suppressed_by_key.pop(evicted_key, None)


def log_rate_limit_warning(
    request: Request,
    client_host: str,
    path: str,
    method: str,
    status_code: int,
) -> None:
    if status_code != status.HTTP_429_TOO_MANY_REQUESTS:
        return
    warning_state = get_rate_limit_warning_state(request)
    if warning_state is None:
        return
    warning_key = f"{client_host}|{path}|{method}"
    current_time = time.monotonic()
    suppressed_count = 0
    should_log = False
    with warning_state.lock:
        previous_time = warning_state.last_logged_by_key.get(warning_key)
        if (
            previous_time is None
            or current_time - previous_time >= _RATE_LIMIT_WARNING_THROTTLE_SECONDS
        ):
            warning_state.last_logged_by_key[warning_key] = current_time
            warning_state.last_logged_by_key.move_to_end(warning_key)
            suppressed_count = warning_state.suppressed_by_key.pop(warning_key, 0)
            should_log = True
        else:
            existing_count = warning_state.suppressed_by_key.get(warning_key, 0)
            warning_state.suppressed_by_key[warning_key] = existing_count + 1
        _evict_stale_rate_limit_entries(warning_state, current_time)
    if not should_log:
        return
    warning_logger = get_logger(LOGGER_NAME)
    if suppressed_count > 0:
        warning_logger.warning(
            "API rate limit exceeded for client '%s' on path '%s' with method '%s'. Suppressed %s additional events.",
            client_host,
            path,
            method,
            suppressed_count,
        )
        return
    warning_logger.warning(
        "API rate limit exceeded for client '%s' on path '%s' with method '%s'.",
        client_host,
        path,
        method,
    )


def get_rate_limit_warning_state(request: Request) -> RateLimitWarningState | None:
    app_state = None
    try:
        app = request.app
    except AttributeError:
        app = None
    if app is not None:
        try:
            app_state = app.state
        except AttributeError:
            app_state = None
    if app_state is None:
        return None
    try:
        existing_state = app_state.api_rate_limit_warning_state
    except AttributeError:
        existing_state = None
    if isinstance(existing_state, RateLimitWarningState):
        return existing_state
    with _get_state_init_lock():
        try:
            existing_state = app_state.api_rate_limit_warning_state
        except AttributeError:
            existing_state = None
        if isinstance(existing_state, RateLimitWarningState):
            return existing_state
        state = RateLimitWarningState(
            lock=threading.Lock(),
            last_logged_by_key=OrderedDict(),
            suppressed_by_key=OrderedDict(),
        )
        app_state.api_rate_limit_warning_state = state
        return state
