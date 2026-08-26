"""SoAI - Dependency bundle for the central configuration manager [backend/app/config/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

__all__ = ("ConfigManagerDependencies",)


@dataclass(frozen=True, slots=True)
class ConfigManagerDependencies:
    base_path: str
    core_config_path: str
    config: ConfigProtocol
    event_bus: EventBusProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    plugin_directory: str | None
    lock_directory: str | None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ConfigManagerDependencies",
            base_path=self.base_path,
            cancellation_binder=self.cancellation_binder,
            config=self.config,
            core_config_path=self.core_config_path,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
        )
