"""SoAI - User repository field coercion helpers [backend/database/repositories/users/user_field_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from core.types.json import JSONValue
from core.validation.boolean_coercion import coerce_bool_with_recovery

__all__ = ("coerce_user_admin_flag",)

LOGGER_NAME = "SoAI.database.repositories.user_field_coercion"


def coerce_user_admin_flag(raw_is_admin: JSONValue) -> bool:
    logger = get_logger(LOGGER_NAME)
    return coerce_bool_with_recovery(
        raw_is_admin,
        logger=logger,
        operation="database_users.coerce_user_admin_flag",
        default=False,
        recover_message="Failed to parse user is_admin flag (non-critical).",
    )
