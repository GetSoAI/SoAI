"""SoAI - Guardian plugin eligibility helpers [backend/plugins/guardian/eligibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.state.state_names import ORCH_STATE_DISABLED, ORCH_STATE_QUARANTINED
from plugins.guardian.candidates import collect_available_guardian_plugin_names
from plugins.guardian.state_snapshot import collect_running_idle_plugin_names

if TYPE_CHECKING:
    from plugins.guardian.check_context import GuardianCheckContext

__all__ = (
    "GUARDIAN_LOGGER_NAME",
    "GuardianIdlePingCandidates",
    "collect_idle_ping_candidate_names",
    "is_plugin_state_health_candidate",
)

GUARDIAN_LOGGER_NAME = "SoAI.plugins.guardian"


@dataclass(frozen=True, slots=True)
class GuardianIdlePingCandidates:
    idle_plugins: list[str]
    persistent_candidates: list[str]


def is_plugin_state_health_candidate(
    check_context: GuardianCheckContext,
    plugin_name: str,
    current_status: str | None,
) -> bool:
    return plugin_name in check_context.unlocked_plugins and current_status not in {
        ORCH_STATE_QUARANTINED,
        ORCH_STATE_DISABLED,
    }


def collect_idle_ping_candidate_names(
    check_context: GuardianCheckContext,
    idle_entries: Iterable[tuple[str, float]],
    *,
    grace_period: float,
    now_monotonic: float,
) -> GuardianIdlePingCandidates:
    base_ping_candidates = collect_available_guardian_plugin_names(check_context)
    idle_candidates = [
        (plugin_name, idle_since)
        for plugin_name, idle_since in idle_entries
        if plugin_name in base_ping_candidates and now_monotonic - idle_since > grace_period
    ]
    idle_plugins = collect_running_idle_plugin_names(
        check_context.plugin_states,
        [plugin_name for plugin_name, _idle_since in idle_candidates],
    )
    idle_names = {plugin_name for plugin_name, _idle_since in idle_candidates}
    persistent_candidates = collect_running_idle_plugin_names(
        check_context.plugin_states,
        [
            plugin_name
            for plugin_name in check_context.plugin_states
            if plugin_name in base_ping_candidates and plugin_name not in idle_names
        ],
    )
    return GuardianIdlePingCandidates(
        idle_plugins=idle_plugins,
        persistent_candidates=persistent_candidates,
    )
