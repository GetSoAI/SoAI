"""SoAI - Task services internal protocols [backend/features/api/runtime/container/protocol_groups/service_protocols/task/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.app.protocols import CancellationSystemProtocol
    from core.tasks.protocols import (
        TaskRegistryProtocol,
        TaskTypeRoutingServiceProtocol,
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
    def cancellation(self) -> CancellationSystemProtocol: ...
