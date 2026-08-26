"""SoAI - Background task internal protocols [backend/app/background/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.automation.protocols_database import (
        DatabaseAutomationRunsProtocol,
        DatabaseAutomationsProtocol,
    )
    from core.licensing.protocols import LicensingStatusProtocol
    from core.tasks.protocols import (
        CancellationHistoryProtocol,
        TaskRegistryProtocol,
        TokenCollectionProtocol,
    )
    from core.tasks.protocols_query import TaskRegistryQueryView

__all__ = (
    "AutomationRunReconciliationDependenciesProtocol",
    "AutomationSchedulingDependenciesProtocol",
)


class AutomationRunReconciliationDependenciesProtocol(Protocol):
    @property
    def database_automation_runs(self) -> DatabaseAutomationRunsProtocol: ...

    @property
    def cancellation_history(self) -> CancellationHistoryProtocol: ...

    @property
    def task_registry(self) -> TaskRegistryProtocol: ...

    @property
    def task_registry_queries(self) -> TaskRegistryQueryView: ...

    @property
    def token_collection(self) -> TokenCollectionProtocol: ...


class AutomationSchedulingDependenciesProtocol(Protocol):
    @property
    def database_automations(self) -> DatabaseAutomationsProtocol: ...

    @property
    def database_automation_runs(self) -> DatabaseAutomationRunsProtocol: ...

    @property
    def licensing_service(self) -> LicensingStatusProtocol: ...
