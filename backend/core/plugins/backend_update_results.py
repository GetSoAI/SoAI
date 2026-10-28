"""SoAI - Backend release check normalization [backend/core/plugins/backend_update_results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.errors.exceptions import ValidationError
from core.errors.payload import ErrorPublicPayload
from core.types.json import JSONDict, JSONValue
from core.validation.strings import require_bounded_trimmed_text

__all__ = (
    "BackendUpdateResult",
    "backend_update_error",
    "normalize_backend_update_result",
)


@dataclass(frozen=True, slots=True)
class BackendUpdateResult:
    status: Literal["current", "update_available", "absent", "check_failed"]
    payload: JSONDict


def backend_update_error(code: str, message: str) -> BackendUpdateResult:
    return BackendUpdateResult(
        "check_failed",
        {
            "update_available": False,
            "current_version": None,
            "latest_version": None,
            "error": ErrorPublicPayload(code=code, message=message).to_dict(),
        },
    )


def _version_alias(payload: JSONDict, names: tuple[str, ...]) -> str | None:
    values: set[str] = set()
    for name in names:
        value = payload.get(name)
        if value is None or value == "":
            continue
        values.add(
            require_bounded_trimmed_text(
                value,
                type_message="Backend version must be text.",
                empty_message="Backend version must not be blank.",
                max_length=1024,
                max_length_message="Backend version is too long.",
            )
        )
    if len(values) > 1:
        raise ValidationError("Backend version aliases disagree.")
    return next(iter(values), None)


def normalize_backend_update_result(
    payload: JSONValue,
    *,
    installed: bool,
) -> BackendUpdateResult:
    if not isinstance(payload, dict):
        return backend_update_error("invalid_response", "Update check returned invalid payload.")
    error = payload.get("error")
    if error is not None:
        if isinstance(error, dict) and error.get("code") == "not_implemented":
            return backend_update_error("not_implemented", "Update check not supported.")
        return backend_update_error("server_error", "Update check failed.")
    if payload.get("status") in ("unavailable", "failed", "error", "check_failed"):
        return backend_update_error("server_error", "Update check is unavailable.")
    available = payload.get("update_available")
    reported_installed = payload.get("installed", installed)
    if not isinstance(available, bool) or not isinstance(reported_installed, bool):
        return backend_update_error("invalid_response", "Update check returned invalid payload.")
    try:
        current = _version_alias(payload, ("current_version", "installed_version"))
        latest = _version_alias(payload, ("latest_version", "available_version", "target_version"))
    except ValidationError:
        return backend_update_error("invalid_response", "Update check returned invalid versions.")
    normalized: JSONDict = {
        **payload,
        "current_version": current,
        "latest_version": latest,
    }
    if not installed or not reported_installed:
        normalized.update({"installed": False, "update_available": False})
        return BackendUpdateResult("absent", normalized)
    return BackendUpdateResult("update_available" if available else "current", normalized)
