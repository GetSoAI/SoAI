"""SoAI - Plugin compatibility helpers for state reporting [backend/core/state/compatibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "CompatibilityInfo",
    "IncompatibilityReason",
    "can_override_incompatibility",
)


class IncompatibilityReason(str, Enum):
    VERSION_INCOMPATIBLE = "VERSION_INCOMPATIBLE"
    OS_INCOMPATIBLE = "OS_INCOMPATIBLE"
    GPU_REQUIRED = "GPU_REQUIRED"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    BROKEN_PLUGIN = "BROKEN_PLUGIN"


@dataclass(slots=True)
class CompatibilityInfo:
    reason: IncompatibilityReason | None
    can_override: bool
    is_overridden: bool
    details: JSONDict
    message: str


OVERRIDABLE_INCOMPATIBILITY_REASONS = frozenset(
    {IncompatibilityReason.OS_INCOMPATIBLE, IncompatibilityReason.GPU_REQUIRED},
)


def can_override_incompatibility(reason: IncompatibilityReason | None) -> bool:
    return bool(reason and reason in OVERRIDABLE_INCOMPATIBILITY_REASONS)
