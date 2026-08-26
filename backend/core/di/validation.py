"""SoAI - Standard dependency validation helpers [backend/core/di/validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.di.protocols import DependencyValueProtocol
from core.errors.exceptions import ValidationError

__all__ = ("require_dependencies",)


def require_dependencies(*, owner: str, **dependencies: DependencyValueProtocol | None) -> None:
    if not owner:
        raise ValidationError("owner must be a non-empty string.", details={"owner": owner})
    missing = sorted([name for name, value in dependencies.items() if value is None])
    if not missing:
        return
    missing_joined = ", ".join(missing)
    raise ValidationError(
        f"{owner} missing required dependencies: {missing_joined}.",
        details={"owner": owner, "missing": missing},
    )
