"""SoAI - CLI application lifecycle runner with signal handling [backend/app/cli/application.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from typing import Literal

from app.application_controller import ApplicationController
from app.application_dependencies import ApplicationEnvironment
from app.builder_dependencies import ApplicationAssemblyBuilderDependencies
from app.cli.application_shutdown import shutdown_application
from app.cli.dependencies import ApplicationDependencies
from app.cli.process_control import setup_signal_handlers
from app.cli.restart_request import (
    cancel_lifecycle_request_watch,
    resolve_lifecycle_request_watch,
    start_lifecycle_request_watch,
)
from app.composition.builder import ApplicationAssemblyBuilder
from app.dependencies import build_application_module_dependencies
from app.edition_composition import EditionComposition
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.bootstrap import emit_gui_status
from core.platform.os import is_windows
from core.timing.monotonic import monotonic_ms
from core.timing.startup_timings import StartupTimingsRecorder

__all__ = ("run_application",)

OPERATION_MAIN_APPLICATION_LOOP = "main.application_loop"


def _load_controller_class() -> type[ApplicationController]:
    controller_cls = ApplicationController
    if not callable(controller_cls):
        raise StateError("Application controller failed to load.")
    return controller_cls


async def run_application(
    dependencies: ApplicationDependencies,
    edition_composition: EditionComposition,
) -> int:
    startup_timings = StartupTimingsRecorder()
    stop_event = asyncio.Event()
    restart_signal_event = threading.Event()
    windows_console_service = setup_signal_handlers(
        asyncio.get_running_loop(),
        stop_event,
        logger=dependencies.lifecycle_logger,
        restart_signal_event=restart_signal_event,
    )
    controller_cls = _load_controller_class()
    environment = ApplicationEnvironment(
        base_dir=dependencies.base_dir,
        config_path=dependencies.config_path,
        main_venv_dir=dependencies.venv_path,
        version=dependencies.version,
    )
    module_dependencies = build_application_module_dependencies()
    assembly_builder = ApplicationAssemblyBuilder(
        ApplicationAssemblyBuilderDependencies(
            environment=environment,
            stop_event=stop_event,
            gui_status=emit_gui_status,
            bootstrap_logger=dependencies.bootstrap_logger,
            lifecycle_logger=dependencies.lifecycle_logger,
            startup_timings=startup_timings,
            module_dependencies=module_dependencies,
            edition_composition=edition_composition,
        ),
    )
    assembly_started_ms = monotonic_ms()
    assembly = await assembly_builder.build()
    startup_timings.record_since_ms("assembly.total_ms", assembly_started_ms)
    application_controller = controller_cls(assembly, startup_timings=startup_timings)
    application_context = application_controller.context
    application_context.runtime.set_pid_lock(dependencies.pid_lock)
    exit_code = 0
    lifecycle_request_task: asyncio.Task[Literal["restart", "stop"] | None] | None = None
    try:
        if is_windows():
            lifecycle_request_task = start_lifecycle_request_watch(
                base_dir=dependencies.base_dir,
                stop_event=stop_event,
                logger=dependencies.lifecycle_logger,
            )
        await application_controller.start()
        if lifecycle_request_task is not None:
            requested_action = await resolve_lifecycle_request_watch(
                lifecycle_request_task,
                stop_event=stop_event,
            )
            if requested_action == "restart":
                application_context.runtime.set_restart_required()
        else:
            await stop_event.wait()
    except asyncio.CancelledError:
        dependencies.lifecycle_logger.info("Main application task cancelled.")
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            dependencies.lifecycle_logger,
            exception,
            message="Unhandled exception in main application loop.",
            operation=OPERATION_MAIN_APPLICATION_LOOP,
            level="critical",
        )
        application_context.runtime.set_critical_shutdown(
            "Unhandled exception in main application loop.",
            1,
        )
        exit_code = 1
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation="main.application_loop")
        log_exception(
            dependencies.lifecycle_logger,
            coerced,
            message="Unexpected exception in main application loop.",
            operation=OPERATION_MAIN_APPLICATION_LOOP,
            level="critical",
        )
        application_context.runtime.set_critical_shutdown(
            "Unexpected exception in main application loop.",
            1,
        )
        exit_code = 1
    finally:
        try:
            await cancel_lifecycle_request_watch(
                lifecycle_request_task,
                logger=dependencies.lifecycle_logger,
            )
            if restart_signal_event.is_set():
                application_context.runtime.set_restart_required()
            exit_code = await shutdown_application(
                application_controller=application_controller,
                base_dir=dependencies.base_dir,
                lifecycle_logger=dependencies.lifecycle_logger,
                restart_cli_module=edition_composition.lifecycle.restart_cli_module,
                exit_code=exit_code,
            )
        finally:
            if windows_console_service is not None:
                windows_console_service.release_ctrl_handler()
    return exit_code
