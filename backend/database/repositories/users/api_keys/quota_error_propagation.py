"""SoAI - API key quota database error propagation [backend/database/repositories/users/api_keys/quota_error_propagation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NoReturn

from core.errors.exceptions import DatabaseError, StateError, ValidationError

__all__ = ("raise_database_cause_if_needed",)


def raise_database_cause_if_needed(exception: DatabaseError) -> NoReturn:
    cause = exception.cause
    if isinstance(cause, ValidationError | StateError):
        raise cause from exception
    raise exception
