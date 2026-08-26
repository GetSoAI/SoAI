"""SoAI - Provider-backed model plugin state availability [backend/core/state/provider_backed_availability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Container
from typing import TYPE_CHECKING

from core.state.health_status import (
    PLUGIN_HEALTH_DISABLED,
    PLUGIN_HEALTH_OPEN,
    PLUGIN_HEALTH_QUARANTINED,
    PLUGIN_HEALTH_RECOVERING,
)
from core.state.state_names import (
    PLUGIN_STATE_BACKEND_INSTALLING,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_BACKEND_UPDATING,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_STOPPED,
)
from core.state.state_transition_sets import UNAVAILABLE_PLUGIN_STATES

if TYPE_CHECKING:
    from core.state.state_names import PluginRuntimeStateName

__all__ = (
    "PROVIDER_BACKED_IGNORED_HEALTH_STATUSES",
    "PROVIDER_BACKED_IGNORED_PLUGIN_STATES",
    "get_provider_aware_unavailable_plugin_states",
    "is_provider_aware_health_available",
)

PROVIDER_BACKED_IGNORED_PLUGIN_STATES: frozenset[PluginRuntimeStateName] = frozenset(
    {
        PLUGIN_STATE_BACKEND_NOT_INSTALLED,
        PLUGIN_STATE_BACKEND_INSTALLING,
        PLUGIN_STATE_BACKEND_UPDATING,
        PLUGIN_STATE_INSTALL_ERROR,
        PLUGIN_STATE_STOPPED,
    },
)
PROVIDER_BACKED_UNAVAILABLE_PLUGIN_STATES: frozenset[PluginRuntimeStateName] = (
    UNAVAILABLE_PLUGIN_STATES - PROVIDER_BACKED_IGNORED_PLUGIN_STATES
)
PLUGIN_HEALTH_BLOCKING_STATUSES: frozenset[str] = frozenset(
    {
        PLUGIN_HEALTH_OPEN,
        PLUGIN_HEALTH_RECOVERING,
        PLUGIN_HEALTH_QUARANTINED,
        PLUGIN_HEALTH_DISABLED,
    },
)
PROVIDER_BACKED_IGNORED_HEALTH_STATUSES: frozenset[str] = frozenset(
    {
        PLUGIN_HEALTH_OPEN,
        PLUGIN_HEALTH_RECOVERING,
    },
)


def get_provider_aware_unavailable_plugin_states(provider_backed: bool) -> Container[str]:
    if provider_backed:
        return PROVIDER_BACKED_UNAVAILABLE_PLUGIN_STATES
    return UNAVAILABLE_PLUGIN_STATES


def is_provider_aware_health_available(health_status: str | None, *, provider_backed: bool) -> bool:
    if health_status is None:
        return True
    blocking_statuses = (
        PLUGIN_HEALTH_BLOCKING_STATUSES - PROVIDER_BACKED_IGNORED_HEALTH_STATUSES
        if provider_backed
        else PLUGIN_HEALTH_BLOCKING_STATUSES
    )
    return health_status not in blocking_statuses
