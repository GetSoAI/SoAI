"""SoAI - Application dependency wiring [backend/app/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import httpx2
import uvicorn
from ruamel import yaml

from app.application_dependencies import (
    ApplicationBootstrapModuleDependencies,
    ApplicationLifecycleModuleDependencies,
    ApplicationLifecycleModuleView,
    ApplicationModuleDependencies,
    ApplicationRuntimeModuleDependencies,
    ApplicationServerModuleDependencies,
    ApplicationStartupModuleDependencies,
    ApplicationUpdaterModuleDependencies,
    EventTypesBundle,
)
from app.lifecycle.signals import register_banner_defaults
from app.server_uvicorn_runtime import SoAIUvicornServer
from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.config.runtime_config import Config
from core.events.types_system import SoAIMainState, SystemRestartRequiredEvent
from core.hardware.speed_test.disk_speed_test_measurement import resolve_existing_path
from core.logging.banner import LogBannerSystem
from core.meta.versioning import build_update_status, normalize_version_string
from core.network.hosts import is_bind_all_interfaces_host
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.validation.boolean_coercion import coerce_bool_with_default
from features.api.middleware.tls import prepare_tls_configuration
from features.api.router import initialize

__all__ = (
    "build_application_module_dependencies",
    "build_updater_module_dependencies",
)


def build_updater_module_dependencies() -> ApplicationUpdaterModuleDependencies:
    return ApplicationUpdaterModuleDependencies(
        httpx2=httpx2,
        config_factory=Config,
        coerce_bool_with_default=coerce_bool_with_default,
        coerce_positive_float=coerce_positive_float,
        build_update_status=build_update_status,
        normalize_version_string=normalize_version_string,
        yaml=yaml,
    )


def build_application_module_dependencies() -> ApplicationModuleDependencies:
    event_types_module = EventTypesBundle(
        system_restart_required_event=SystemRestartRequiredEvent,
        soai_main_state=SoAIMainState,
    )
    lifecycle = ApplicationLifecycleModuleDependencies(
        banner_width=70,
        register_banner_defaults=register_banner_defaults,
        log_banner_system_factory=LogBannerSystem,
    )
    runtime = ApplicationRuntimeModuleDependencies(
        application_lifecycle=ApplicationLifecycleModuleView(
            banner_width=lifecycle.banner_width,
            register_banner_defaults=lifecycle.register_banner_defaults,
        ),
        event_types=event_types_module,
        log_banner_system_factory=lifecycle.log_banner_system_factory,
    )
    server = ApplicationServerModuleDependencies(
        api_initialize=initialize,
        prepare_tls_configuration=prepare_tls_configuration,
        spawn_tracked_task=spawn_tracked_task,
        uvicorn=uvicorn,
        uvicorn_server_factory=SoAIUvicornServer,
    )
    startup = ApplicationStartupModuleDependencies(
        event_types=event_types_module,
        is_bind_all_interfaces_host=is_bind_all_interfaces_host,
        resolve_speed_test_path=resolve_existing_path,
    )
    bootstrap = ApplicationBootstrapModuleDependencies(
        coerce_positive_int=coerce_positive_int,
    )
    updater = build_updater_module_dependencies()
    return ApplicationModuleDependencies(
        runtime=runtime,
        server=server,
        startup=startup,
        lifecycle=lifecycle,
        bootstrap=bootstrap,
        updater=updater,
    )
