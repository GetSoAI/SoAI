"""SoAI - Plugin health check loop with automated recovery [backend/plugins/guardian_loop.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import secrets
import time

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_system import SoAIMainState, SystemMainStateOverrideEvent
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from plugins.guardian.check_context import build_guardian_check_context
from plugins.guardian.check_runner import (
    GUARDIAN_LOGGER_NAME,
    run_guardian_recovery_checks,
)
from plugins.guardian.health_config import resolve_guardian_health_check_config
from plugins.guardian.recovery_scheduler import schedule_guardian_recovery_tasks
from plugins.guardian_checks.idle_reconciliation import reconcile_idle_plugins
from plugins.guardian_checks.plugin_state_health import update_health_metrics
from plugins.protocols_internal.guardian.internal_protocols import (
    PluginGuardianInternalProtocol,
)

__all__ = ()

OPERATION_PLUGIN_GUARDIAN_GUARDIAN_HEALTH_CHECK_LOOP = "plugin_guardian.guardianhealth_check_loop"


async def _application_shutdown_in_progress(self: PluginGuardianInternalProtocol) -> bool:
    main_state = await self.state_aggregator.get_main_state()
    return main_state.get("state") == SoAIMainState.STOPPING.value


def _compute_guardian_sleep_delay(
    interval: float,
    jitter_fraction: float,
    random_fraction: float,
) -> float:
    clamped_jitter = min(max(jitter_fraction, 0.0), 1.0)
    computed_sleep = interval + interval * clamped_jitter * (random_fraction - 0.5) * 2
    return max(0.05, computed_sleep)


async def health_check_loop(self: PluginGuardianInternalProtocol) -> None:
    logger = get_logger(GUARDIAN_LOGGER_NAME)
    while not self.shutdown_event.is_set():
        try:
            health_config = resolve_guardian_health_check_config(self.routing_config.health_checks)
            shutdown_requested = False
            try:
                await asyncio.wait_for(
                    self.shutdown_event.wait(),
                    timeout=_compute_guardian_sleep_delay(
                        health_config.interval,
                        health_config.jitter,
                        secrets.SystemRandom().random(),
                    ),
                )
                shutdown_requested = True
            except TimeoutError:
                shutdown_requested = False
            if shutdown_requested or self.shutdown_event.is_set():
                break
            if await _application_shutdown_in_progress(self):
                break
            check_context = await build_guardian_check_context(self)
            if self.shutdown_event.is_set():
                break
            now_monotonic = time.monotonic()
            plugins_to_recover = await run_guardian_recovery_checks(
                self,
                check_context=check_context,
                health_config=health_config,
                now_monotonic=now_monotonic,
            )
            if self.shutdown_event.is_set():
                break
            try:
                await reconcile_idle_plugins(
                    self,
                    check_context=check_context,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Guardian idle reconciliation failed for current iteration",
                    operation=OPERATION_PLUGIN_GUARDIAN_GUARDIAN_HEALTH_CHECK_LOOP,
                    level="warning",
                )
            accepted_recoveries = await schedule_guardian_recovery_tasks(
                self,
                check_context=check_context,
                plugins_to_recover=plugins_to_recover,
                logger=logger,
            )
            try:
                await update_health_metrics(
                    self,
                    check_context=check_context,
                    recovering_plugins=accepted_recoveries,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Guardian health metric update failed for current iteration",
                    operation=OPERATION_PLUGIN_GUARDIAN_GUARDIAN_HEALTH_CHECK_LOOP,
                    level="warning",
                )
        except asyncio.CancelledError:
            break
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Critical error in guardian health check loop",
                operation=OPERATION_PLUGIN_GUARDIAN_GUARDIAN_HEALTH_CHECK_LOOP,
                level="critical",
            )
            _ = self.component_context.spawn_tracked_task(
                self.bus.publish(
                    SystemMainStateOverrideEvent(
                        state=SoAIMainState.ERROR,
                        duration_sec=10,
                        reason=f"Critical error in Plugin Guardian: {exception}",
                    ),
                ),
                name="plugin-guardian-state-override",
                logger=logger,
                cancellation_binder=self.cancellation_binder,
                finalizer_tracker=self.component_context.finalizer_tracker,
                cancellation_id=create_system_id(
                    subsystem="plugin_guardian_override",
                    owner="main_state",
                    include_random_suffix=True,
                ),
                owner="plugin_guardian_override",
                metadata={"reason": str(exception)},
            )
