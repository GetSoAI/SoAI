"""SoAI - Scheduler requirement mismatch failure reason formatting [backend/orchestrator/scheduling/requirement_failure_reasons.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from orchestrator.scheduling.plugin_requirements import RequirementEvaluation

__all__ = (
    "format_requirements_failure_reason",
    "format_virtual_model_requirements_failure_reason",
)


def format_requirements_failure_reason(
    *,
    model_label: str,
    plugin_name: str | None,
    missing_capabilities: tuple[str, ...],
    missing_modalities: tuple[str, ...],
    required_capabilities: tuple[str, ...],
    required_modalities: tuple[str, ...],
) -> str:
    parts: list[str] = []
    if missing_modalities:
        parts.append(f"Missing modalities: {', '.join(missing_modalities)}.")
    if missing_capabilities:
        parts.append(f"Missing capabilities: {', '.join(missing_capabilities)}.")
    requirements: list[str] = []
    if required_modalities:
        requirements.append(f"modalities {', '.join(required_modalities)}")
    if required_capabilities:
        requirements.append(f"capabilities {', '.join(required_capabilities)}")
    requirements_label = ", ".join(requirements) if requirements else "the requested requirements"
    plugin_label = f" on plugin '{plugin_name}'" if plugin_name else ""
    parts.append(
        f"Selected model '{model_label}'{plugin_label} does not support {requirements_label}.",
    )
    parts.append("Fix: select a compatible model or adjust the request.")
    return " ".join(parts)


def format_virtual_model_requirements_failure_reason(
    *,
    virtual_model_name: str,
    required_capabilities: tuple[str, ...],
    required_modalities: tuple[str, ...],
    evaluation_results: list[RequirementEvaluation],
) -> str:
    required_caps = {token for token in required_capabilities if token}
    required_mods = {token for token in required_modalities if token}
    supported_caps_union: set[str] = set()
    supported_mods_union: set[str] = set()
    for evaluation in evaluation_results:
        supported_caps_union.update(required_caps.difference(evaluation.missing_capabilities))
        supported_mods_union.update(required_mods.difference(evaluation.missing_modalities))
    missing_caps_global = tuple(sorted(required_caps.difference(supported_caps_union)))
    missing_mods_global = tuple(sorted(required_mods.difference(supported_mods_union)))
    requirements: list[str] = []
    if required_modalities:
        requirements.append(f"modalities {', '.join(required_modalities)}")
    if required_capabilities:
        requirements.append(f"capabilities {', '.join(required_capabilities)}")
    requirements_label = ", ".join(requirements) if requirements else "the requested requirements"
    message_parts: list[str] = [
        f"Virtual model '{virtual_model_name}' has no eligible member that supports {requirements_label}.",
    ]
    if missing_mods_global:
        message_parts.append(
            f"Unsupported modalities across all members: {', '.join(missing_mods_global)}.",
        )
    if missing_caps_global:
        message_parts.append(
            f"Unsupported capabilities across all members: {', '.join(missing_caps_global)}.",
        )
    if not missing_mods_global and not missing_caps_global and evaluation_results:
        message_parts.append(
            "No single member supports the requested combination of modalities/capabilities.",
        )
    message_parts.append("Fix: update the virtual model membership or select a compatible model.")
    return " ".join(message_parts)
