"""SoAI - Actionable GPU inventory contention [backend/core/hardware/gpu_inventory_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import (
    ServiceUnavailableError,
    SoAIError,
    SoAITimeoutError,
    ValidationError,
)
from core.types.dict import freeze_json_dict
from core.types.json import JSONValue

if TYPE_CHECKING:
    from typing import Literal

    type GPUInventoryQueryFailureReason = Literal[
        "native_timeout",
        "native_exit",
        "empty_response",
        "invalid_response",
        "runtime_unavailable",
        "permission_denied",
        "query_unavailable",
        "caller_deadline",
        "admission_deadline",
        "shared_deadline",
    ]


__all__ = (
    "GPUInventoryBusyError",
    "GPUObservationSupersededError",
    "GPUObservationUnavailableError",
    "GPUInventoryTimeoutError",
    "gpu_inventory_query_failure",
    "require_gpu_discovery_capabilities",
)


_QUERY_FAILURE_MESSAGES: tuple[tuple[GPUInventoryQueryFailureReason, str], ...] = (
    (
        "native_timeout",
        "The native GPU discovery query timed out. Wait for discovery to settle, then retry.",
    ),
    (
        "native_exit",
        "The native GPU discovery query failed. Check the graphics driver and system diagnostics, then retry.",
    ),
    (
        "empty_response",
        "The native GPU discovery query returned no data. Check the graphics driver, then retry.",
    ),
    (
        "invalid_response",
        "The native GPU discovery query returned invalid data. Check the graphics driver and system diagnostics, then retry.",
    ),
    (
        "runtime_unavailable",
        "The GPU discovery runtime is unavailable. Restore the system discovery tools, then retry.",
    ),
    (
        "permission_denied",
        "GPU discovery was denied permission. Check the service account's hardware access, then retry.",
    ),
    (
        "query_unavailable",
        "GPU discovery is unavailable. Check the graphics driver and system discovery tools, then retry.",
    ),
    (
        "caller_deadline",
        "GPU discovery timed out while waiting for a hardware query. Wait for it to settle, then retry.",
    ),
    (
        "admission_deadline",
        "GPU discovery is waiting for an outstanding hardware query. Wait for it to settle, then retry.",
    ),
    (
        "shared_deadline",
        "GPU discovery timed out while waiting for a shared hardware query. Wait for it to settle, then retry.",
    ),
)


class GPUInventoryTimeoutError(SoAITimeoutError, TimeoutError):
    code: str | int = "gpu_inventory_timeout"
    public_message: str | None = (
        "GPU discovery timed out. An outstanding hardware query may still be finishing. Wait for it to settle, then retry."
    )


def gpu_inventory_query_failure(
    reason: GPUInventoryQueryFailureReason,
    *,
    cause: BaseException | None = None,
    details: Mapping[str, JSONValue] | None = None,
    diagnostic_message: str | None = None,
) -> SoAIError:
    public_message = next(
        (message for known_reason, message in _QUERY_FAILURE_MESSAGES if known_reason == reason),
        None,
    )
    if public_message is None:
        raise ValidationError("GPU discovery failure reason is invalid.")
    timed_out = reason in (
        "native_timeout",
        "caller_deadline",
        "admission_deadline",
        "shared_deadline",
    )
    error = (
        GPUInventoryTimeoutError(diagnostic_message or public_message, details=details, cause=cause)
        if timed_out
        else ServiceUnavailableError(
            diagnostic_message or public_message, details=details, cause=cause
        )
    )
    if not timed_out:
        error.code = "gpu_inventory_query_failed"
    error.public_message = public_message
    error.public_details = {"reason": reason}
    return error


def require_gpu_discovery_capabilities(capabilities: Mapping[str, JSONValue]) -> None:
    discovery = capabilities.get("gpu_discovery")
    if discovery is None:
        return
    if not isinstance(discovery, dict) or discovery.get("status") != "unavailable":
        raise ValidationError("GPU discovery capability outcome is invalid.")
    error = discovery.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    if code == "gpu_inventory_busy":
        details = error.get("details") if isinstance(error, dict) else None
        if isinstance(details, dict) and details.get("reason") == "topology_changed":
            raise GPUObservationSupersededError("GPU inventory changed during discovery.")
        raise GPUInventoryBusyError("GPU discovery is busy.")
    if code == "gpu_observation_unavailable":
        raise GPUObservationUnavailableError("GPU observation is unavailable.")
    details = error.get("details") if isinstance(error, dict) else None
    reason = details.get("reason") if isinstance(details, dict) else None
    for known_reason, _message in _QUERY_FAILURE_MESSAGES:
        if reason == known_reason:
            raise gpu_inventory_query_failure(known_reason)
    raise ValidationError("GPU discovery capability failure reason is invalid.")


class GPUInventoryBusyError(ServiceUnavailableError):
    code: str | int = "gpu_inventory_busy"
    public_message: str | None = (
        "GPU identity observation is busy or recovering. Wait for inventory to settle and retry this history series."
    )


class GPUObservationSupersededError(GPUInventoryBusyError, TimeoutError):
    __slots__ = ()
    public_message: str | None = (
        "GPU inventory changed during discovery. Wait for hardware detection to settle, then retry."
    )
    public_details: Mapping[str, JSONValue] | None = freeze_json_dict(
        {"reason": "topology_changed"}
    )


class GPUObservationUnavailableError(ServiceUnavailableError):
    code: str | int = "gpu_observation_unavailable"
    public_message: str | None = (
        "Live GPU state could not be observed. Saved changes remain durable. Wait for observation to recover, then refresh."
    )
