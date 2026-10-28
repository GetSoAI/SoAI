"""SoAI - WebUI request validation helpers [backend/features/api/routes/webui/request_validators.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.users.user_id import coerce_optional_user_id
from features.api.runtime.current_user import CurrentUser
from features.api.runtime.errors import raise_server_error

__all__ = ("require_user_id",)


def require_user_id(request: Request, current_user: CurrentUser) -> int:
    user_id = coerce_optional_user_id(current_user.get("id"))
    if user_id is not None and user_id > 0:
        return user_id
    raise_server_error(request, "Current user id is invalid.")
