"""SoAI - Application bootstrap state dataclass [backend/app/composition/application_bootstrap_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.composition.bootstrap_state_core import BootstrapStateCore
from app.types_services_foundation import (
    ConfigurationServices,
    InfrastructureServices,
    TaskServices,
)

if TYPE_CHECKING:
    from tasks.registry.queries import TaskRegistryQueries
    from tasks.registry.registry import TaskRegistry

__all__ = ("ApplicationBootstrapState",)


@dataclass(frozen=True, slots=True)
class ApplicationBootstrapState(BootstrapStateCore):
    task_registry: TaskRegistry
    task_registry_queries: TaskRegistryQueries
    infrastructure_services: InfrastructureServices
    configuration_services: ConfigurationServices
    task_services: TaskServices
