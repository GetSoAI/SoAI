"""SoAI - Current user identity validation for WebUI routes [backend/features/api/routes/webui/user_identity_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.errors.exceptions import ValidationError
from core.users.username import require_canonical_username
from features.api.runtime.current_user import CurrentUser
from features.api.runtime.errors import raise_invalid_request

__all__ = ("require_username",)


def require_username(request: Request, current_user: CurrentUser) -> str:
    username_value = current_user.get("username")
    if isinstance(username_value, str):
        try:
            return require_canonical_username(username_value)
        except ValidationError:
            raise_invalid_request(request, "Authenticated user is missing a username.")
    raise_invalid_request(request, "Authenticated user is missing a username.")
