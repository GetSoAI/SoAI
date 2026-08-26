"""SoAI - Assembly-time service precondition helpers [backend/app/composition/service_preconditions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError

__all__ = ("require_initialized",)


def require_initialized[T](value: T | None, *, message: str) -> T:
    if value is None:
        raise StateError(message)
    return value
