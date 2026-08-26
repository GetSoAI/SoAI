"""SoAI - Automation internal protocol definitions [backend/features/automation/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.automation.protocols_database import DatabaseAutomationRunsProtocol
    from core.tasks.protocols import TaskRegistryProtocol

__all__ = ("AutomationRunTerminalDependenciesProtocol",)


class AutomationRunTerminalDependenciesProtocol(Protocol):
    @property
    def database_automation_runs(self) -> DatabaseAutomationRunsProtocol: ...

    @property
    def task_registry(self) -> TaskRegistryProtocol: ...
