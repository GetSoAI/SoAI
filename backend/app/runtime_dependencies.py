"""SoAI - Application runtime dependency bundle [backend/app/runtime_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from app.application_dependencies import (
    ApplicationLogging,
    ApplicationRuntimeModuleDependencies,
)
from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.config.runtime_config import Config
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggingManagerProtocol
    from core.orchestrator.protocols_lifecycle import (
        CoreRoutingConfigApplicatorProtocol,
    )
    from core.runtime.protocols import (
        RuntimeFlagsMutationProtocol,
        RuntimeFlagsViewProtocol,
        RuntimeStateStoreProtocol,
    )
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = ("ApplicationRuntimeCoordinatorDependencies",)


@dataclass(slots=True, frozen=True)
class ApplicationRuntimeCoordinatorDependencies:
    logging: ApplicationLogging
    runtime_state: RuntimeStateStoreProtocol
    configuration: Config | None
    event_bus: EventBusProtocol | None
    logging_manager: LoggingManagerProtocol | None
    http_client: httpx2.AsyncClient | None
    runtime_flags: RuntimeFlagsMutationProtocol
    module_dependencies: ApplicationRuntimeModuleDependencies
    finalizer_tracker: TaskFinalizerTrackerProtocol
    task_cancellation_binder: TaskCancellationBinderProtocol
    core_routing_applicator: CoreRoutingConfigApplicatorProtocol | None = None
    update_plugin_worker_runtime_flags: (
        Callable[[RuntimeFlagsViewProtocol], Awaitable[None]] | None
    ) = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationRuntimeCoordinatorDependencies",
            finalizer_tracker=self.finalizer_tracker,
            logging=self.logging,
            module_dependencies=self.module_dependencies,
            runtime_flags=self.runtime_flags,
            runtime_state=self.runtime_state,
            task_cancellation_binder=self.task_cancellation_binder,
        )
        if not isinstance(
            self.module_dependencies,
            ApplicationRuntimeModuleDependencies,
        ):
            raise ValidationError("ApplicationRuntimeModuleDependencies are required.")
