"""SoAI - Lifecycle result records [backend/app/lifecycle/results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "LifecycleFailure",
    "LifecycleRunError",
)


@dataclass(frozen=True, slots=True)
class LifecycleFailure:
    component_name: str
    phase: str
    critical: bool
    message: str


class LifecycleRunError(RuntimeError):
    def __init__(self, failure: LifecycleFailure) -> None:
        super().__init__(failure.message)
        self.failure: LifecycleFailure = failure
