"""SoAI - Bootstrap dependency requirement checks [backend/app/composition/bootstrap_requirements.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError

__all__ = ("require_initialized_dependency",)


def require_initialized_dependency[TDependency](
    value: TDependency | None,
    label: str,
) -> TDependency:
    if value is None:
        raise StateError(f"{label} is required but was not initialized.")
    return value
