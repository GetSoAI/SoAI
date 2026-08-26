"""SoAI - Inactivity monitor action profile resolution [backend/orchestrator/inactivity_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from orchestrator.inactivity_settings import InactivityMonitorSettings
from orchestrator.inactivity_workflow import InactivityActionSpec

__all__ = (
    "InactivityWorkflowProfile",
    "build_model_inactivity_profile",
    "build_system_inactivity_profile",
)


@dataclass(frozen=True, slots=True)
class InactivityWorkflowProfile:
    timeout_seconds: float
    action_spec: InactivityActionSpec


def build_system_inactivity_profile(
    settings: InactivityMonitorSettings,
) -> InactivityWorkflowProfile:
    if settings.system_action == "shutdown":
        return InactivityWorkflowProfile(
            timeout_seconds=settings.system_timeout_seconds,
            action_spec=InactivityActionSpec(
                log_level="warning",
                message=(
                    f"System inactive for {settings.system_timeout_seconds / 60:.1f} minutes. "
                    "Initiating shutdown..."
                ),
                audit_action="INACTIVITY_SHUTDOWN",
                audit_target="system",
                audit_reason="system_inactivity",
                metrics_label="shutdown",
            ),
        )
    if settings.system_action == "unload_models":
        return InactivityWorkflowProfile(
            timeout_seconds=settings.system_timeout_seconds,
            action_spec=InactivityActionSpec(
                log_level="info",
                message=(
                    f"System inactive for {settings.system_timeout_seconds / 60:.1f} minutes. "
                    "Unloading all models..."
                ),
                audit_action="INACTIVITY_UNLOAD_MODELS",
                audit_target="all_models",
                audit_reason="system_inactivity",
                metrics_label="unload_models",
            ),
        )
    raise ValidationError(f"Unsupported inactivity system action: {settings.system_action}")


def build_model_inactivity_profile(
    settings: InactivityMonitorSettings,
) -> InactivityWorkflowProfile:
    return InactivityWorkflowProfile(
        timeout_seconds=settings.models_timeout_seconds,
        action_spec=InactivityActionSpec(
            log_level="info",
            message=(
                f"Models inactive for {settings.models_timeout_seconds / 60:.1f} "
                "minutes. Unloading all models..."
            ),
            audit_action="INACTIVITY_UNLOAD_MODELS",
            audit_target="all_models",
            audit_reason="model_inactivity",
            metrics_label="unload_models",
        ),
    )
