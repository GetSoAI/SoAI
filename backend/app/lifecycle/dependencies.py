"""SoAI - Dependency bundles for application lifecycle services [backend/app/lifecycle/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.application_dependencies import ApplicationLifecycleModuleDependencies
from core.di.validation import require_dependencies
from core.logging.protocols import LoggerProtocol
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TokenCollectionProtocol,
)

__all__ = ("DiscoveryServerDependencies",)


@dataclass(frozen=True, slots=True)
class DiscoveryServerDependencies:
    logger_supplier: Callable[[], LoggerProtocol]
    token_collection: TokenCollectionProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    module_dependencies: ApplicationLifecycleModuleDependencies

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DiscoveryServerDependencies",
            cancellation_event_bus=self.cancellation_event_bus,
            cancellation_binder=self.cancellation_binder,
            cancellation_history=self.cancellation_history,
            finalizer_tracker=self.finalizer_tracker,
            logger_supplier=self.logger_supplier,
            module_dependencies=self.module_dependencies,
            token_collection=self.token_collection,
        )
