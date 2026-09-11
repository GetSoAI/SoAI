"""SoAI - Startup finalization and readiness transition [backend/app/startup_steps/finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import platform
import time
import webbrowser
from dataclasses import dataclass

from app.background.chat_stream_registry_reaper import run_chat_stream_registry_reaper
from app.startup_beep import emit_startup_beep_if_enabled
from app.startup_steps.dependencies import StartupStepDependencies
from app.types_application import ApplicationContext
from app.updater.software_update.activation import commit_ready_update_activation
from app.updater.software_update.activation_state import find_pending_update_activation
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.network.urls import build_host_port_url
from core.runtime.environment_flags import is_soai_no_browser
from core.tasks.software_update_result import (
    prepare_software_update_activation_task,
    reconcile_software_update_result,
)
from core.timing.constants import BACKGROUND_TIMEOUT_SEC, RESPONSIVE_TIMEOUT_SEC, STANDARD_DELAY_SEC
from core.timing.monotonic import monotonic_ms

__all__ = ("StartupFinalizationStep",)

OPERATION_APPLICATION_STARTUP_FINALIZE_STARTUP_BACKUP_START = (
    "application_startup.finalize_startup.backup_start"
)
OPERATION_APPLICATION_STARTUP_OPEN_BROWSER_DELAYED = "application_startup.open_browser_delayed"
OPERATION_APPLICATION_STARTUP_STARTUP = "application_startup.startup"


@dataclass(frozen=True, slots=True)
class StartupFinalizationStep:
    deps: StartupStepDependencies

    def resolve_browser_controller(
        self,
    ) -> tuple[webbrowser.BaseBrowser | None, str | None]:
        if platform.system() == "Linux" and (
            not (os.environ.get("DISPLAY", "") or os.environ.get("WAYLAND_DISPLAY", ""))
        ):
            return (None, "no graphical display detected")
        try:
            controller = webbrowser.get()
        except webbrowser.Error:
            return (None, "no default browser configured")
        try:
            browser_name = controller.name
        except AttributeError:
            browser_name = ""
        if not browser_name:
            browser_name = controller.__class__.__name__
        normalized_name = browser_name.lower()
        if normalized_name in {"lynx", "links", "elinks", "w3m"}:
            return (None, f"text-mode browser '{browser_name}'")
        return (controller, None)

    async def finalize_startup(self, application_context: ApplicationContext) -> None:
        transition_scheduled_ms = monotonic_ms()
        servers_present = application_context.services.lifecycle.coordinator.has_servers()
        if servers_present:
            application_context.logging.logger.debug(
                "Waiting for %s server(s) to confirm startup...",
                application_context.services.lifecycle.coordinator.server_count(),
            )
            try:
                await application_context.services.lifecycle.coordinator.wait_until_started(30.0)
                application_context.logging.logger.debug("All servers have confirmed startup.")
            except (StateError, TimeoutError) as exception:
                log_exception(
                    application_context.logging.logger,
                    exception,
                    message="One or more API/WebUI servers failed to start within the timeout",
                    operation=OPERATION_APPLICATION_STARTUP_STARTUP,
                )
                raise StateError(
                    "One or more API/WebUI servers failed to confirm startup.",
                ) from exception
        application_context.logging.logger.info("SoAI running with PID %s.", os.getpid())
        configuration = application_context.services.configuration.config
        state_aggregator = application_context.services.infrastructure.state_aggregator
        if configuration is None or state_aggregator is None:
            raise StateError(
                "Configuration and state aggregator must be initialized before startup completion.",
            )
        runtime_flags = application_context.services.configuration.runtime_flags
        host_system_actions_allowed = (
            runtime_flags is None or not runtime_flags.host_system_actions_disabled
        )
        auto_open_requested = (
            application_context.runtime.webui_available
            and self.deps.runtime_coordinator.get_configuration_flag(
                "SERVER.WEBUI.AUTO_OPEN_BROWSER",
                True,
            )
            and (not is_soai_no_browser())
            and host_system_actions_allowed
        )
        browser_open: tuple[webbrowser.BaseBrowser, str] | None = None
        if auto_open_requested and servers_present:
            controller, skip_reason = self.resolve_browser_controller()
            if controller:
                runtime_api_endpoint = application_context.runtime.runtime_api_endpoint
                if runtime_api_endpoint is None:
                    raise StateError("Runtime API endpoint is unavailable for browser launch.")
                url = build_host_port_url(
                    runtime_api_endpoint.scheme,
                    runtime_api_endpoint.local_connect_host,
                    runtime_api_endpoint.effective_port,
                )
                application_context.logging.logger.info(
                    "Attempting to open the SoAI WebUI in your default browser at %s...",
                    url,
                )
                browser_open = (controller, url)
            elif skip_reason:
                application_context.logging.logger.info(
                    "Skipping automatic browser launch: %s.",
                    skip_reason,
                )
        elif auto_open_requested:
            application_context.logging.logger.info(
                "Skipping automatic browser launch: Unified server is not running.",
            )
        await state_aggregator.set_main_state(
            self.deps.module_dependencies.event_types.soai_main_state.STARTING,
            "startup_complete",
        )

        async def transition_from_starting() -> None:
            transition_started_ms = monotonic_ms()
            if (
                application_context.runtime.shutdown_event.is_set()
                or application_context.runtime.system_stop_event.is_set()
            ):
                return
            await asyncio.sleep(STANDARD_DELAY_SEC)
            if (
                application_context.runtime.shutdown_event.is_set()
                or application_context.runtime.system_stop_event.is_set()
            ):
                return
            if servers_present:
                application_context.services.lifecycle.coordinator.require_servers_serving()
            application_context.logging.logger.info(
                "Finalizing startup and syncing state before announcing readiness.",
            )
            self.deps.startup_timings.record_since_ms(
                "startup.transition_delay_ms",
                transition_scheduled_ms,
            )
            if (
                application_context.runtime.shutdown_event.is_set()
                or application_context.runtime.system_stop_event.is_set()
            ):
                return
            pending_update = find_pending_update_activation(application_context.paths.base_dir)
            if pending_update is not None:
                await prepare_software_update_activation_task(
                    application_context.services.tasks.task_registry,
                    base_path=application_context.paths.base_dir,
                    task_id=pending_update.task_id,
                    from_version=pending_update.from_version,
                    to_version=pending_update.to_version,
                )
            activated_update = commit_ready_update_activation(
                base_path=application_context.paths.base_dir,
                edition=application_context.edition_composition.updater.edition,
                product_version=application_context.edition_composition.updater.product_version,
                config_path=application_context.paths.config_path,
                repair_plane=application_context.runtime.repair_plane,
                logger=application_context.logging.logger,
            )
            if not application_context.runtime.set_startup_ready():
                application_context.logging.logger.info(
                    "Startup readiness announcement skipped because shutdown has begun.",
                )
                return
            if activated_update:
                await reconcile_software_update_result(
                    application_context.services.tasks.task_registry,
                    base_path=application_context.paths.base_dir,
                )
            if (
                application_context.runtime.shutdown_event.is_set()
                or application_context.runtime.system_stop_event.is_set()
            ):
                return
            if application_context.services.storage.backup_service is not None:
                try:
                    await application_context.services.storage.backup_service.start(
                        wait_for_startup_ready=True,
                    )
                except RECOVERABLE_EXCEPTIONS as backup_start_exception:
                    log_exception(
                        application_context.logging.logger,
                        backup_start_exception,
                        message="BackupManager start failed",
                        operation=OPERATION_APPLICATION_STARTUP_FINALIZE_STARTUP_BACKUP_START,
                    )
            if (
                application_context.runtime.shutdown_event.is_set()
                or application_context.runtime.system_stop_event.is_set()
            ):
                return
            messaging_gateway = application_context.services.infrastructure.messaging_gateway
            if messaging_gateway is not None:
                reconciliation_completed = await messaging_gateway.wait_for_initial_reconciliation(
                    BACKGROUND_TIMEOUT_SEC,
                )
                if not reconciliation_completed:
                    application_context.logging.logger.warning(
                        "Messaging Gateway initial reconciliation is still pending; admission remains closed.",
                    )
                if (
                    application_context.runtime.shutdown_event.is_set()
                    or application_context.runtime.system_stop_event.is_set()
                ):
                    return
            recalc_started_ms = monotonic_ms()
            transitioned_state = await state_aggregator.recalculate_and_set_main_state(
                "post_startup_transition",
            )
            self.deps.startup_timings.record_since_ms(
                "startup.transition_recalculate_state_ms",
                recalc_started_ms,
            )
            application_context.logging.gui_status(
                "SoAI repair plane is ready."
                if application_context.runtime.repair_plane
                else "SoAI is ready!"
            )
            ready_state = self.deps.module_dependencies.event_types.soai_main_state.READY
            if transitioned_state == ready_state:
                await emit_startup_beep_if_enabled(
                    configuration,
                    application_context.logging.logger,
                )
            self.deps.startup_timings.record_since_ms(
                "startup.transition_total_ms",
                transition_started_ms,
            )
            self.deps.startup_timings.record_elapsed_ms("startup.ready_total_ms")

            application_context.logging.logger.info(
                "Application startup completed in %.2fs",
                time.monotonic() - application_context.runtime.startup_time,
            )
            metrics_manager = application_context.services.infrastructure.metrics_manager
            if metrics_manager is not None:
                startup_duration_ms = max(
                    0,
                    monotonic_ms() - int(float(application_context.runtime.startup_time) * 1000),
                )
                metrics_manager.record_timing(
                    "global",
                    "timings",
                    "startup_duration_ms",
                    duration_ms=float(startup_duration_ms),
                )

            application_context.logging.logger.debug(
                "STARTUP_TIMINGS: %s",
                self.deps.startup_timings.payload_json(),
            )
            self.deps.runtime_coordinator.schedule_background_task(
                run_chat_stream_registry_reaper(application_context),
                name="chat-stream-registry-reaper",
            )
            self.deps.runtime_coordinator.ensure_banner_system().emit("ready")

        await transition_from_starting()
        if browser_open is not None and application_context.runtime.startup_ready_event.is_set():
            controller, url = browser_open

            async def open_browser_delayed() -> None:
                try:
                    await asyncio.sleep(RESPONSIVE_TIMEOUT_SEC)
                    if runtime_flags is not None and runtime_flags.host_system_actions_disabled:
                        application_context.logging.logger.info(
                            "Skipping automatic browser launch: host system actions are disabled.",
                        )
                        return
                    if not application_context.runtime.shutdown_event.is_set():
                        await asyncio.to_thread(controller.open_new_tab, url)
                except asyncio.CancelledError:
                    return
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_exception(
                        application_context.logging.logger,
                        exception,
                        message="Automatic browser open failed (this is normal in headless environments).",
                        operation=OPERATION_APPLICATION_STARTUP_OPEN_BROWSER_DELAYED,
                        details={"url": url},
                        level="warning",
                    )

            browser_task_coroutine = open_browser_delayed()
            if (
                self.deps.runtime_coordinator.schedule_background_task(
                    browser_task_coroutine,
                    name="open-browser",
                )
                is None
            ):
                browser_task_coroutine.close()
