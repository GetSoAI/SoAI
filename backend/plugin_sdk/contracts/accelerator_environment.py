"""SoAI - Plugin SDK accelerator environment helpers [backend/plugin_sdk/contracts/accelerator_environment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from plugin_sdk.contracts.accelerator_binding import build_accelerator_binding_environment
from plugin_sdk.contracts.config_access import get_config_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("build_accelerator_environment",)

_ACCELERATOR_VISIBILITY_ENV_KEYS = (
    "CUDA_VISIBLE_DEVICES",
    "NVIDIA_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "ROCR_VISIBLE_DEVICES",
    "HSA_VISIBLE_DEVICES",
    "ROCM_VISIBLE_DEVICES",
    "GGML_VK_VISIBLE_DEVICES",
    "ZE_AFFINITY_MASK",
)


def build_accelerator_environment(
    plugin_config: Mapping[str, JSONValue],
    *,
    base_environment: Mapping[str, str] | None = None,
    gpu_inventory: Mapping[str, JSONValue] | None = None,
    runtime_family: str = "none",
) -> dict[str, str]:
    environment = dict(base_environment) if base_environment is not None else os.environ.copy()
    for key in _ACCELERATOR_VISIBILITY_ENV_KEYS:
        environment.pop(key, None)
    environment.update(
        build_accelerator_binding_environment(
            plugin_config,
            gpu_inventory=gpu_inventory,
            runtime_family=runtime_family,
        ),
    )
    hsa_override = (
        get_config_str(
            plugin_config,
            "HSA_OVERRIDE_GFX_VERSION",
            default=None,
        )
        or ""
    )
    if hsa_override:
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,2}", hsa_override) is None:
            raise ValidationError(
                "HSA_OVERRIDE_GFX_VERSION must use a numeric AMD GFX override such as '10.3.0'.",
            )
        environment["HSA_OVERRIDE_GFX_VERSION"] = hsa_override
    return environment
