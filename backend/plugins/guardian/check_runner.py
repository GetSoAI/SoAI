"""SoAI - Guardian health check aggregation [backend/plugins/guardian/check_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from plugins.guardian.eligibility import GUARDIAN_LOGGER_NAME
from plugins.guardian.recovery_decisions import collect_guardian_recovery_decisions
from plugins.guardian_checks.hanging_request_detection import check_hanging_requests
from plugins.guardian_checks.idle_plugin_ping import ping_idle_plugins
from plugins.guardian_checks.plugin_state_health import check_plugin_states

if TYPE_CHECKING:
    from plugins.guardian.check_context import GuardianCheckContext
    from plugins.guardian.health_config import GuardianHealthCheckConfig
    from plugins.protocols_internal.guardian.internal_protocols import (
        PluginGuardianInternalProtocol,
    )

__all__ = (
    "GUARDIAN_LOGGER_NAME",
    "run_guardian_recovery_checks",
)


async def run_guardian_recovery_checks(
    self: PluginGuardianInternalProtocol,
    *,
    check_context: GuardianCheckContext,
    health_config: GuardianHealthCheckConfig,
    now_monotonic: float,
) -> dict[str, str]:
    check_results = await asyncio.gather(
        check_hanging_requests(
            self,
            check_context=check_context,
            now=now_monotonic,
            streaming_idle_timeout=health_config.streaming_idle_timeout,
            non_streaming_timeout=health_config.non_streaming_timeout,
        ),
        check_plugin_states(
            self,
            check_context=check_context,
            now_monotonic=now_monotonic,
            stuck_state_timeout=health_config.stuck_state_timeout,
            flapping_window=health_config.flapping_window,
            flapping_min_transitions=health_config.flapping_min_transitions,
        ),
        ping_idle_plugins(
            self,
            check_context=check_context,
            ping_timeout=health_config.ping_timeout,
            grace_period=health_config.idle_ping_grace_period,
            now_monotonic=now_monotonic,
        ),
        return_exceptions=True,
    )
    return collect_guardian_recovery_decisions(
        check_names=("hanging_requests", "plugin_states", "idle_ping"),
        check_results=check_results,
        logger=get_logger(GUARDIAN_LOGGER_NAME),
    )
