"""SoAI - API application initialization and rate-limit state setup [backend/features/api/router.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import FastAPI

from core.errors.exceptions import StateError
from core.rate_limiting.moving_window import MovingWindowRateLimiter
from features.api.app_factory import build_api_app
from features.api.rate_limiting.runtime_state import ensure_rate_limit_runtime_state

__all__ = ("initialize",)


def initialize() -> FastAPI:
    app = build_api_app()
    try:
        request_rate_limiter = app.state.request_rate_limiter
    except AttributeError:
        request_rate_limiter = MovingWindowRateLimiter()
        app.state.request_rate_limiter = request_rate_limiter
    if not isinstance(request_rate_limiter, MovingWindowRateLimiter):
        raise StateError("request_rate_limiter is invalid.")
    ensure_rate_limit_runtime_state(app.state, request_rate_limiter)
    return app
