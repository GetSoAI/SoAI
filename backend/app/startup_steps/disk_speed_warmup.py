"""SoAI - Startup disk speed test warmup [backend/app/startup_steps/disk_speed_warmup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.startup_steps.dependencies import StartupStepDependencies
from app.types_application import ApplicationContext
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS

__all__ = ("DiskSpeedWarmupStep",)

OPERATION_APPLICATION_STARTUP_DISK_SPEED_WARMUP_LOAD_PLUGIN = (
    "application_startup.disk_speed_warmup.load_plugin"
)
OPERATION_APPLICATION_STARTUP_DISK_SPEED_WARMUP_MODELS_DIRECTORY = (
    "application_startup.disk_speed_warmup.models_directory"
)
OPERATION_APPLICATION_STARTUP_DISK_SPEED_WARMUP_SPEED_TEST = (
    "application_startup.disk_speed_warmup.speed_test"
)
OPERATION_APPLICATION_STARTUP_PRIME_DISK_SPEED_TESTS = "application_startup.prime_disk_speed_tests"


@dataclass(frozen=True, slots=True)
class DiskSpeedWarmupStep:
    deps: StartupStepDependencies

    async def prime_disk_speed_tests(self, application_context: ApplicationContext) -> None:
        if (
            application_context.services.databases.plugins is None
            or application_context.services.plugins.plugin_manager is None
        ):
            return
        try:
            plugin_rows = await application_context.services.databases.plugins.get_all_plugins()
        except RECOVERABLE_EXCEPTIONS as error:
            log_exception(
                application_context.logging.logger,
                error,
                message="Disk speed warmup inventory failed",
                operation=OPERATION_APPLICATION_STARTUP_PRIME_DISK_SPEED_TESTS,
                level="warning",
            )
            return
        seen_paths: set[str] = set()
        plugin_manager_instance = application_context.services.plugins.plugin_manager
        if plugin_manager_instance is None:
            return
        for row in plugin_rows:
            plugin_name = row.get("plugin_name")
            if not isinstance(plugin_name, str) or not plugin_name:
                continue
            try:
                instance = await plugin_manager_instance.get_plugin_instance(plugin_name)
            except RECOVERABLE_EXCEPTIONS as load_error:
                log_exception(
                    application_context.logging.logger,
                    load_error,
                    message="Disk speed warmup skipped (plugin load failed).",
                    operation=OPERATION_APPLICATION_STARTUP_DISK_SPEED_WARMUP_LOAD_PLUGIN,
                    details={"plugin_name": plugin_name},
                    level="warning",
                )
                continue
            if not instance:
                continue
            try:
                models_directory = instance.get_models_directory()
            except ValidationError:
                continue
            except RECOVERABLE_EXCEPTIONS as path_error:
                log_exception(
                    application_context.logging.logger,
                    path_error,
                    message="Disk speed warmup directory error.",
                    operation=OPERATION_APPLICATION_STARTUP_DISK_SPEED_WARMUP_MODELS_DIRECTORY,
                    details={"plugin_name": plugin_name},
                    level="warning",
                )
                continue
            if not models_directory:
                continue
            resolved = (
                self.deps.module_dependencies.resolve_speed_test_path(models_directory)
                or models_directory
            )
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            try:
                await application_context.services.infrastructure.hardware.manager.build_variant_support_context(
                    resolved,
                    True,
                    database_hardware=application_context.services.databases.hardware,
                    http_client=None,
                )
            except RECOVERABLE_EXCEPTIONS as speed_error:
                log_exception(
                    application_context.logging.logger,
                    speed_error,
                    message="Disk speed warmup failed.",
                    operation=OPERATION_APPLICATION_STARTUP_DISK_SPEED_WARMUP_SPEED_TEST,
                    details={"resolved_path": resolved},
                    level="warning",
                )
