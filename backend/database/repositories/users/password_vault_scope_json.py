"""SoAI - Password vault scope JSON helpers [backend/database/repositories/users/password_vault_scope_json.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.web.site_scope import SiteScope
from core.web.site_scope_codec import (
    parse_site_scope_json_str,
    serialize_site_scope_json,
)

__all__ = (
    "parse_password_vault_scope_json",
    "serialize_password_vault_scope_json",
)


def serialize_password_vault_scope_json(scope: SiteScope) -> str:
    return serialize_site_scope_json(scope)


def parse_password_vault_scope_json(value: str) -> SiteScope:
    try:
        return parse_site_scope_json_str(value)
    except ValueError as exception:
        raise StateError(str(exception)) from exception
