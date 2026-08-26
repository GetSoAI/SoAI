"""SoAI - Plugin manager lifecycle policy models and construction [backend/plugins/manager/policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from core.state.compatibility import IncompatibilityReason
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_ERROR,
    ORCH_STATE_QUARANTINED,
    ORCHESTRATOR_STATE_NAMES_WITHOUT_UNKNOWN,
    PLUGIN_STATE_BACKEND_INSTALLING,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
    PLUGIN_STATE_BACKEND_UPDATING,
    PLUGIN_STATE_DELETE_ERROR,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_LOAD_ERROR,
    PLUGIN_STATE_PERSISTENT_READY,
    PLUGIN_STATE_REMOVING_BACKEND,
    PLUGIN_STATE_STOPPED,
    PLUGIN_STATE_UPDATE_ERROR,
)

if TYPE_CHECKING:
    from core.state.state_names import PluginRuntimeStateName

__all__ = (
    "LifecycleActionPolicy",
    "PluginManagerPolicy",
    "build_plugin_manager_policy",
)


@dataclass(frozen=True, slots=True)
class LifecycleActionPolicy:
    transient: PluginRuntimeStateName
    final: PluginRuntimeStateName
    error: PluginRuntimeStateName


@dataclass(frozen=True, slots=True)
class PluginManagerPolicy:
    lifecycle_action_config: MappingProxyType[str, LifecycleActionPolicy]
    installed_states: frozenset[str]
    allowed_actions_by_state: MappingProxyType[PluginRuntimeStateName, frozenset[str]]
    hardware_incompatible_reasons: frozenset[IncompatibilityReason]
    startup_reset_states: frozenset[str]


def build_plugin_manager_policy() -> PluginManagerPolicy:
    lifecycle_action_config: MappingProxyType[str, LifecycleActionPolicy] = MappingProxyType(
        {
            "install_backend": LifecycleActionPolicy(
                transient=PLUGIN_STATE_BACKEND_INSTALLING,
                final=PLUGIN_STATE_STOPPED,
                error=PLUGIN_STATE_INSTALL_ERROR,
            ),
            "update_backend": LifecycleActionPolicy(
                transient=PLUGIN_STATE_BACKEND_UPDATING,
                final=PLUGIN_STATE_STOPPED,
                error=PLUGIN_STATE_UPDATE_ERROR,
            ),
            "remove_backend": LifecycleActionPolicy(
                transient=PLUGIN_STATE_REMOVING_BACKEND,
                final=PLUGIN_STATE_BACKEND_NOT_INSTALLED,
                error=PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
            ),
        },
    )
    installed_states: frozenset[str] = frozenset(
        (
            PLUGIN_STATE_STOPPED,
            PLUGIN_STATE_PERSISTENT_READY,
            *ORCHESTRATOR_STATE_NAMES_WITHOUT_UNKNOWN,
        ),
    )
    allowed_actions_by_state: MappingProxyType[PluginRuntimeStateName, frozenset[str]] = (
        MappingProxyType(
            {
                ORCH_STATE_DISABLED: frozenset(
                    ("enable", "delete", "force_cleanup", "remove_backend"),
                ),
                PLUGIN_STATE_BACKEND_NOT_INSTALLED: frozenset(
                    ("enable", "disable", "install_backend", "delete", "force_cleanup", "clone"),
                ),
                ORCH_STATE_QUARANTINED: frozenset(
                    ("delete", "force_cleanup", "reset_circuit_breaker"),
                ),
                PLUGIN_STATE_INSTALL_ERROR: frozenset(
                    (
                        "enable",
                        "disable",
                        "install_backend",
                        "remove_backend",
                        "delete",
                        "force_cleanup",
                        "clone",
                    ),
                ),
                PLUGIN_STATE_LOAD_ERROR: frozenset(
                    (
                        "enable",
                        "disable",
                        "delete",
                        "force_cleanup",
                        "clone",
                    ),
                ),
                PLUGIN_STATE_UPDATE_ERROR: frozenset(
                    (
                        "enable",
                        "disable",
                        "update_backend",
                        "remove_backend",
                        "delete",
                        "force_cleanup",
                        "clone",
                    ),
                ),
                PLUGIN_STATE_BACKEND_UNINSTALL_ERROR: frozenset(
                    (
                        "enable",
                        "disable",
                        "install_backend",
                        "remove_backend",
                        "delete",
                        "force_cleanup",
                        "clone",
                    ),
                ),
                PLUGIN_STATE_DELETE_ERROR: frozenset(
                    (
                        "enable",
                        "disable",
                        "delete",
                        "force_cleanup",
                        "clone",
                    ),
                ),
            },
        )
    )
    hardware_incompatible_reasons = frozenset(
        (
            IncompatibilityReason.OS_INCOMPATIBLE,
            IncompatibilityReason.GPU_REQUIRED,
        ),
    )
    startup_reset_states = frozenset((ORCH_STATE_ERROR,))
    return PluginManagerPolicy(
        lifecycle_action_config=lifecycle_action_config,
        installed_states=installed_states,
        allowed_actions_by_state=allowed_actions_by_state,
        hardware_incompatible_reasons=hardware_incompatible_reasons,
        startup_reset_states=startup_reset_states,
    )
