"""SoAI - Lifecycle entry definitions [backend/app/lifecycle/entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError

__all__ = ("LifecycleEntry",)


@dataclass(frozen=True, slots=True)
class LifecycleEntry:
    component_name: str
    phase: str
    action: Callable[[], Awaitable[None]]
    timeout_sec: float
    critical: bool = True

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LifecycleEntry",
            action=self.action,
            component_name=self.component_name,
            phase=self.phase,
        )
        if self.timeout_sec < 0:
            raise ValidationError("Lifecycle timeout must be non-negative.")
