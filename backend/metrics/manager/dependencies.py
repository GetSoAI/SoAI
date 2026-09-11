"""SoAI - MetricsManager dependencies dataclass [backend/metrics/manager/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.hardware.protocols import DatabaseHardwareProtocol
from core.metrics.protocols import DatabaseMetricsProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol

if TYPE_CHECKING:
    from core.lifecycle.protocols import ServiceLifecycleProtocol

__all__ = ("MetricsManagerDependencies",)


@dataclass(frozen=True, slots=True)
class MetricsManagerDependencies:
    config: ConfigProtocol
    database_metrics: DatabaseMetricsProtocol
    database_hardware: DatabaseHardwareProtocol
    database_plugins: DatabasePluginsProtocol
    lifecycle: ServiceLifecycleProtocol
    event_bus: EventBusProtocol | None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MetricsManagerDependencies",
            config=self.config,
            database_hardware=self.database_hardware,
            database_metrics=self.database_metrics,
            database_plugins=self.database_plugins,
            lifecycle=self.lifecycle,
        )
