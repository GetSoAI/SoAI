"""SoAI - Dependency-based API rate limit enforcement [backend/features/api/rate_limiting/rate_limit_dependency.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from starlette.requests import HTTPConnection, Request

from core.logging.trace import get_logger
from features.api.rate_limiting.rate_limit_evaluator import (
    ApiRateLimitExceeded,
    evaluate_rate_limit,
)
from features.api.rate_limiting.rate_limit_notifications import (
    notify_rate_limit_breach_noncritical,
)
from features.api.runtime.context import resolve_api_context

__all__ = ("rate_limit_dependency",)

LOGGER_NAME = "SoAI.features.api.rate_limit_dependency"


async def rate_limit_dependency(connection: HTTPConnection) -> None:
    if not isinstance(connection, Request):
        return
    request = connection
    route_obj = request.scope.get("route")
    if route_obj is None:
        return
    try:
        route_path = route_obj.path
    except AttributeError:
        route_path = None
    try:
        route_path_format = route_obj.path_format
    except AttributeError:
        route_path_format = None
    breach = await evaluate_rate_limit(request, route_path, route_path_format)
    if breach is None:
        return
    request.state.rate_limit_breach = breach
    api_context = resolve_api_context(request)
    await notify_rate_limit_breach_noncritical(
        database_notifications=api_context.dependencies.database_notifications,
        breach=breach,
        log=get_logger(LOGGER_NAME),
        operation="features.api.rate_limiting.notify_breach",
    )
    raise ApiRateLimitExceeded(breach)
