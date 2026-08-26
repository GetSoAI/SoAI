"""SoAI - Centralized config hot-reload policy and change classification [backend/core/config/reload_coordinator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.protocols import (
    CoreConfigReloadClassification,
    CoreConfigReloadEventProtocol,
    CoreConfigReloadResult,
    ReloadRejectionReason,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "CoreConfigReloadClassification",
    "CoreConfigReloadCoordinator",
    "CoreConfigReloadResult",
    "ReloadRejectionReason",
    "classify_core_config_reload",
)

HOT_RELOADABLE_CORE_SECTIONS: frozenset[str] = frozenset(
    {"MODELS.ROUTING", "API.OPENAI.RATE_LIMITING", "SYSTEM.RUNTIME"},
)


def classify_core_config_reload(
    changed_keys: frozenset[str],
    config_dict: JSONDict,
    revision: int,
) -> CoreConfigReloadClassification:
    non_hot_reloadable = changed_keys - HOT_RELOADABLE_CORE_SECTIONS
    requires_restart = bool(non_hot_reloadable) if changed_keys else False
    return CoreConfigReloadClassification(
        revision=revision,
        changed_keys=changed_keys,
        has_routing_changes="MODELS.ROUTING" in changed_keys or not changed_keys,
        has_rate_limiting_changes="API.OPENAI.RATE_LIMITING" in changed_keys or not changed_keys,
        requires_restart=requires_restart,
        config_dict=config_dict,
    )


class CoreConfigReloadCoordinator:
    def __init__(self) -> None:
        self.last_revision: int = 0

    def try_accept_reload(self, event: CoreConfigReloadEventProtocol) -> CoreConfigReloadResult:
        if event.config_name != "core":
            return CoreConfigReloadResult(
                classification=None,
                rejection_reason=ReloadRejectionReason.NOT_CORE_CONFIG,
            )
        if event.revision <= self.last_revision:
            return CoreConfigReloadResult(
                classification=None,
                rejection_reason=ReloadRejectionReason.STALE_REVISION,
            )
        if not isinstance(event.config_dict, dict):
            return CoreConfigReloadResult(
                classification=None,
                rejection_reason=ReloadRejectionReason.INVALID_PAYLOAD,
            )
        classification = classify_core_config_reload(
            changed_keys=event.changed_keys,
            config_dict=event.config_dict,
            revision=event.revision,
        )
        self.last_revision = event.revision
        return CoreConfigReloadResult(
            classification=classification,
            rejection_reason=None,
        )
