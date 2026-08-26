"""SoAI - ApplicationAssemblyBuilder dependency bundle [backend/app/builder_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.application_dependencies import ApplicationEnvironment, ApplicationModuleDependencies
from app.edition_composition import EditionComposition
from core.di.validation import require_dependencies
from core.timing.startup_timings import StartupTimingsRecorder

__all__ = ("ApplicationAssemblyBuilderDependencies",)


@dataclass(frozen=True, slots=True)
class ApplicationAssemblyBuilderDependencies:
    environment: ApplicationEnvironment
    stop_event: asyncio.Event
    gui_status: Callable[[str], None]
    bootstrap_logger: logging.Logger
    lifecycle_logger: logging.Logger
    startup_timings: StartupTimingsRecorder
    module_dependencies: ApplicationModuleDependencies
    edition_composition: EditionComposition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationAssemblyBuilderDependencies",
            bootstrap_logger=self.bootstrap_logger,
            environment=self.environment,
            gui_status=self.gui_status,
            lifecycle_logger=self.lifecycle_logger,
            module_dependencies=self.module_dependencies,
            edition_composition=self.edition_composition,
            startup_timings=self.startup_timings,
            stop_event=self.stop_event,
        )
