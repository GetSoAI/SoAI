"""SoAI - Plugin environment requirement normalization [backend/plugins/environments/requirements.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from packaging.requirements import InvalidRequirement, Requirement

from core.errors.exceptions import ValidationError

__all__ = ("normalize_plugin_requirements",)


def normalize_plugin_requirements(requirements: list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for requirement_text in requirements:
        candidate = str(requirement_text or "").strip()
        if not candidate:
            continue
        if candidate.startswith("-"):
            raise ValidationError(f"Unsafe plugin dependency specifier '{candidate}'.")
        try:
            requirement = Requirement(candidate)
        except InvalidRequirement as exception:
            raise ValidationError(
                f"Invalid plugin dependency specifier '{candidate}'.",
            ) from exception
        if requirement.marker and not requirement.marker.evaluate():
            continue
        normalized.append(str(requirement))
    return tuple(sorted(set(normalized)))
