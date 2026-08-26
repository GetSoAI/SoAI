"""SoAI - Runtime banner system initialization [backend/app/runtime_banner_setup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from app.banner_system import resolve_banner_system
from core.logging.colors import LOG_BANNER_DEFAULTS

if TYPE_CHECKING:
    from app.runtime_dependencies import ApplicationRuntimeCoordinatorDependencies
    from core.logging.protocols import LogBannerSystemProtocol

__all__ = ("ensure_banner_system",)


def ensure_banner_system(
    deps: ApplicationRuntimeCoordinatorDependencies,
) -> tuple[ApplicationRuntimeCoordinatorDependencies, LogBannerSystemProtocol]:
    logging_context = deps.logging
    logging_manager_instance = deps.logging_manager
    lifecycle_module = deps.module_dependencies.application_lifecycle
    log_banner_system_factory = deps.module_dependencies.log_banner_system_factory
    banner_system = resolve_banner_system(
        logger=logging_context.logger,
        banner_width=lifecycle_module.banner_width,
        current_banner_system=logging_context.banner_system,
        logging_manager=logging_manager_instance,
        banner_system_factory=log_banner_system_factory,
        register_defaults=lambda system: lifecycle_module.register_banner_defaults(
            system,
            list(LOG_BANNER_DEFAULTS),
        ),
    )
    updated_logging = replace(logging_context, banner_system=banner_system)
    updated_deps = replace(deps, logging=updated_logging)
    return updated_deps, banner_system
