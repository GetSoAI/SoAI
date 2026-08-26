"""SoAI - Application lifecycle failure state recording [backend/app/lifecycle/failure_recording.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.lifecycle.results import LifecycleFailure
from app.types_application import ApplicationContext

__all__ = ("record_critical_lifecycle_failures",)


def record_critical_lifecycle_failures(
    application_context: ApplicationContext,
    failures: list[LifecycleFailure],
) -> None:
    for failure in failures:
        if not failure.critical:
            continue
        application_context.runtime.set_critical_shutdown(failure.message, 1)
