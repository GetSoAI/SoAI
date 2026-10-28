"""SoAI - Backend variant compatibility metadata and guidance [backend/core/plugins/backend_variant_compatibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exceptions import ValidationError
from core.hardware.native_compatibility_assessment import (
    NativeCompatibilityAssessment,
    assess_native_compatibility,
)
from core.types.json import JSONDict, JSONValue

__all__ = ("copy_variant_compatibility_requirements", "assess_backend_variant_options")


def copy_variant_compatibility_requirements(
    target: JSONDict, source: Mapping[str, JSONValue]
) -> None:
    requirements = source.get("compatibility_requirements")
    if requirements is None:
        return
    artifact_tag = source.get("compatibility_artifact_tag")
    configuration = source.get("compatibility_configuration")
    invalid_artifact = not isinstance(artifact_tag, str) or not artifact_tag.strip()
    if (
        not isinstance(requirements, dict)
        or invalid_artifact
        or not isinstance(configuration, dict)
    ):
        raise ValidationError("Backend variant compatibility requirements have invalid identity.")
    if not configuration or not all(
        isinstance(value, str) and value for value in configuration.values()
    ):
        raise ValidationError("Backend variant compatibility requirements have invalid identity.")
    target["compatibility_requirements"] = dict(requirements)
    target["compatibility_artifact_tag"] = artifact_tag
    target["compatibility_configuration"] = dict(configuration)


def assess_backend_variant_options(
    options: list[JSONDict],
    *,
    capabilities: Mapping[str, JSONValue],
    configuration: Mapping[str, JSONValue],
    inventory: Mapping[str, JSONValue] | None,
) -> list[JSONDict]:
    assessed_options: list[JSONDict] = []
    for option in options:
        assessed = dict(option)
        requirements = option.get("compatibility_requirements")
        if isinstance(requirements, dict):
            expected_configuration = option.get("compatibility_configuration")
            if not isinstance(expected_configuration, dict) or any(
                configuration.get(key) != value for key, value in expected_configuration.items()
            ):
                assessment = NativeCompatibilityAssessment("unknown", ("requirements_incomplete",))
            else:
                assessment = assess_native_compatibility(
                    requirements,
                    capabilities,
                    gpu_binding=configuration.get("GPU_BINDING"),
                    gpu_inventory=inventory,
                )
            assessed["compatibility"] = assessment.to_dict()
        assessed_options.append(assessed)
    return assessed_options
