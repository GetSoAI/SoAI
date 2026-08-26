"""SoAI - Licensing mutation moving-window admission [backend/features/api/routes/webui/licensing_rate_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math

from fastapi import Request

from core.errors.exceptions import ValidationError
from core.rate_limiting.definitions import RateLimitRule
from core.rate_limiting.moving_window import MovingWindowRateLimiter
from core.timing.epoch import epoch_seconds_float
from features.api.runtime.client_host import resolve_client_host
from features.api.runtime.errors import raise_rate_limit


def _rate_limit_rule(operation_group: str) -> RateLimitRule:
    if operation_group == "online":
        return RateLimitRule(6, 600, "Licensing online operations")
    if operation_group == "import":
        return RateLimitRule(10, 60, "Licensing certificate imports")
    if operation_group == "completion":
        return RateLimitRule(5, 900, "Licensing setup completion")
    if operation_group == "cheap":
        return RateLimitRule(30, 60, "Licensing draft mutations")
    raise ValidationError("Licensing rate-limit operation group is invalid.")


def enforce_licensing_mutation_rate(request: Request, operation_group: str) -> None:
    rule = _rate_limit_rule(operation_group)
    limiter = request.app.state.request_rate_limiter
    if not isinstance(limiter, MovingWindowRateLimiter):
        raise ValidationError("Licensing mutation rate limiter is unavailable.")
    client_ip = resolve_client_host(request, default="") or "unknown"
    decision = limiter.hit(
        rules=(rule,),
        client_key=f"licensing:{client_ip}",
        scope_key=f"licensing:{operation_group}",
    )
    if decision.allowed:
        return
    stats = decision.stats
    if stats is None:
        raise ValidationError("Licensing mutation rate limiter returned an invalid decision.")
    retry_after_seconds = max(
        1,
        math.ceil(stats.reset_epoch_seconds - epoch_seconds_float()),
    )
    raise_rate_limit(
        request,
        "Too many licensing attempts. Please try again later.",
        error_type="licensing_rate_limited",
        extra={"retry_after_seconds": retry_after_seconds},
        headers={"Retry-After": str(retry_after_seconds)},
    )


__all__ = ("enforce_licensing_mutation_rate",)
