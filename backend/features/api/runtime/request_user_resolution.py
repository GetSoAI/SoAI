"""SoAI - Request user ID resolution [backend/features/api/runtime/request_user_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.runtime.protocols import RequestProtocol
from core.users.user_id import coerce_user_id

__all__ = ("resolve_request_user_id",)


def resolve_request_user_id(request: RequestProtocol) -> int:
    context = request.state.context
    try:
        user_id_value = context.user_id
    except AttributeError:
        user_id_value = None
    return coerce_user_id(user_id_value)
