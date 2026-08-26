"""SoAI - Startup lifecycle entry construction [backend/app/lifecycle/startup_entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from app.lifecycle.entries import LifecycleEntry
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from app.startup_steps.dependencies import StartupStepDependencies

__all__ = ("startup_entry", "timed_startup_entry")


def startup_entry(
    *,
    component_name: str,
    action: Callable[[], Awaitable[None]],
) -> LifecycleEntry:
    return LifecycleEntry(
        component_name=component_name,
        phase="startup",
        action=action,
        timeout_sec=LONG_REQUEST_TIMEOUT_SEC,
        critical=True,
    )


def timed_startup_entry(
    *,
    component_name: str,
    metric_key: str,
    deps: StartupStepDependencies,
    action: Callable[[], Awaitable[None]],
) -> LifecycleEntry:
    async def _run() -> None:
        step_started_ms = monotonic_ms()
        await action()
        deps.startup_timings.record_since_ms(metric_key, step_started_ms)

    return startup_entry(component_name=component_name, action=_run)
