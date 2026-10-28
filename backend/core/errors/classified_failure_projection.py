"""SoAI - Public projection of reason-classified startup failures [backend/core/errors/classified_failure_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ConfigurationError, ValidationError
from core.errors.payload import ErrorPublicPayload

if TYPE_CHECKING:
    from core.errors.exceptions import SoAIError
    from core.types.json import JSONDict

__all__ = ("project_classified_failure",)

CLASSIFIED_FAILURE_CODES = frozenset((ConfigurationError.code, ValidationError.code))
CLASSIFIED_FAILURE_MESSAGES = (
    (
        "gpu_binding_identity_conflict",
        "The selected GPU has duplicate physical identities in the hardware inventory. Refresh hardware information and select the GPU again.",
    ),
    (
        "vulkan_runtime_unavailable",
        "Selected GPU binding needs Vulkan device mapping, but the Vulkan tools are unavailable or failed. Install the distribution Vulkan tools and driver, or bind all GPUs.",
    ),
    (
        "vulkan_query_timeout",
        "Selected GPU binding needs Vulkan device mapping, but the Vulkan device query timed out. Check the Vulkan driver, or bind all GPUs.",
    ),
    (
        "vulkan_format_unsupported",
        "Selected GPU binding needs Vulkan device mapping, but the Vulkan tools returned an unsupported format. Update the distribution Vulkan tools, or bind all GPUs.",
    ),
    (
        "vulkan_device_unavailable",
        "The selected GPU is not among the Vulkan devices. Check the Vulkan driver for this GPU, or select a different GPU.",
    ),
    (
        "vulkan_identity_unavailable",
        "The selected GPU shares no UUID or PCI identity with the Vulkan devices, so it cannot be bound safely. Bind all GPUs instead.",
    ),
    (
        "vulkan_identity_conflict",
        "The selected GPU has conflicting identity in the Vulkan device list, so it cannot be bound safely. Check the GPU drivers, or bind all GPUs.",
    ),
    (
        "vulkan_device_ambiguous",
        "The selected GPU is exposed by several Vulkan drivers. Remove the duplicate Vulkan driver (ICD), or bind all GPUs.",
    ),
    (
        "model_configuration_missing",
        "The GGUF model needs its original model configuration. Place the original config.json next to the GGUF file or set the Hugging Face config path, then retry.",
    ),
    (
        "model_architecture_unsupported",
        "The selected backend does not support this model architecture. Use another version of the model or another backend.",
    ),
    (
        "model_tool_calling_unsupported",
        "The selected model does not support tool calling. Select a model that supports tools, or disable tools for this request.",
    ),
    (
        "cuda_device_architecture_unsupported",
        "The installed CUDA backend cannot run on the selected NVIDIA GPU architecture. Select a supported GPU, install a CUDA backend variant that supports this GPU, or use a CPU backend.",
    ),
    (
        "native_cpu_features_unsupported",
        "This processor lacks CPU instructions that the installed backend variant requires. Install a compatible backend variant, such as CPU.",
    ),
    (
        "openvino_tensor_shape_incompatible",
        "The OpenVINO backend could not run this model because its graph tensor shapes are incompatible. Use another backend variant for this model, or set GPU layers to zero for CPU execution.",
    ),
)
MAX_DETAIL_TEXT_LENGTH = 128
MAX_DETAIL_LIST_LENGTH = 16


def project_classified_failure(
    error: SoAIError,
    *,
    trace_id: str | None,
) -> ErrorPublicPayload | None:
    if error.code not in CLASSIFIED_FAILURE_CODES:
        return None
    source = error.details or {}
    reason = source.get("reason")
    message = next(
        (message for code, message in CLASSIFIED_FAILURE_MESSAGES if code == reason), None
    )
    if reason is None or message is None:
        return None
    details: JSONDict = {"reason": reason}
    for name in ("device_id", "model_type"):
        value = source.get(name)
        if isinstance(value, str) and 0 < len(value) <= MAX_DETAIL_TEXT_LENGTH:
            details[name] = value
    indices = source.get("vulkan_indices")
    if isinstance(indices, list) and all(
        isinstance(index, int) and not isinstance(index, bool) for index in indices
    ):
        details["vulkan_indices"] = list(indices)
    features = source.get("missing_cpu_features")
    if (
        isinstance(features, list)
        and 0 < len(features) <= MAX_DETAIL_LIST_LENGTH
        and all(
            isinstance(feature, str) and 0 < len(feature) <= MAX_DETAIL_TEXT_LENGTH
            for feature in features
        )
    ):
        details["missing_cpu_features"] = list(features)
    return ErrorPublicPayload(
        code=str(reason),
        message=message,
        details=details,
        http_status=int(error.http_status),
        trace_id=trace_id,
    )
