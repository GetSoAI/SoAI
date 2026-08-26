"""SoAI - Task services internal protocols [backend/features/api/runtime/container/protocol_groups/service_protocols/task/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.tasks.protocols import (
        CancellationCoordinatorProtocol,
        CancellationEventBusProtocol,
        CancellationHistoryProtocol,
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TaskRegistryProtocol,
        TaskTypeRoutingServiceProtocol,
        TokenCollectionProtocol,
    )
    from core.tasks.protocols_query import TaskRegistryQueryView

__all__ = ("TaskServicesProtocol",)


class TaskServicesProtocol(Protocol):
    @property
    def task_registry(self) -> TaskRegistryProtocol: ...

    @property
    def task_registry_queries(self) -> TaskRegistryQueryView: ...

    @property
    def task_type_routing_service(self) -> TaskTypeRoutingServiceProtocol: ...

    @property
    def cancellation_coordinator(self) -> CancellationCoordinatorProtocol: ...

    @property
    def cancellation_history(self) -> CancellationHistoryProtocol: ...

    @property
    def cancellation_event_bus(self) -> CancellationEventBusProtocol: ...

    @property
    def token_collection(self) -> TokenCollectionProtocol: ...

    @property
    def task_cancellation_binder(self) -> TaskCancellationBinderProtocol: ...

    @property
    def task_finalizer_tracker(self) -> TaskFinalizerTrackerProtocol: ...
