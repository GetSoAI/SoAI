"""SoAI - API runtime current user resolution [backend/features/api/runtime/current_user.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request, status

from core.errors.exceptions import ApiError
from core.types.json import is_json_dict
from features.api.runtime.context import require_request_context
from features.api.runtime.user_coercion import coerce_current_user
from features.api.runtime.user_types import CurrentUser

__all__ = ("CurrentUser", "get_current_user", "get_optional_current_user")


def get_optional_current_user(request: Request) -> CurrentUser | None:
    try:
        user_value = request.state.user
    except AttributeError:
        user_value = None
    if not is_json_dict(user_value):
        return None
    return coerce_current_user(user_value)


async def get_current_user(request: Request) -> CurrentUser:
    current_user = get_optional_current_user(request)
    if current_user is not None:
        return current_user
    request_context = require_request_context(request)
    trace_id = request_context.trace_id
    raise ApiError(
        "Could not validate credentials",
        code="authentication_error",
        http_status=status.HTTP_401_UNAUTHORIZED,
        operation="api_runtime.get_current_user",
        trace_id=trace_id,
    )
