"""SoAI - API runtime user serialization [backend/features/api/runtime/users_serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sanitize_user_response",)

_PUBLIC_USER_FIELDS: tuple[str, ...] = (
    "id",
    "username",
    "is_admin",
    "workspace_path",
    "workspace_path_resolved",
    "default_workspace_path",
    "identity_revision",
)


def sanitize_user_response(user: JSONDict) -> JSONDict:
    sanitized_user: JSONDict = {}
    for field_name in _PUBLIC_USER_FIELDS:
        field_value = user.get(field_name)
        if field_value is not None:
            sanitized_user[field_name] = field_value
    return sanitized_user
