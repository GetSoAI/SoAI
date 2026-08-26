"""SoAI - Plugin action response payload container [backend/plugins/action_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.errors.exceptions import InsufficientDiskSpaceError
    from core.types.json import JSONDict

__all__ = (
    "PluginActionResponse",
    "accepted_plugin_action_response",
    "insufficient_disk_space_response",
    "network_policy_violation_response",
)


@dataclass(slots=True)
class PluginActionResponse:
    success: bool
    status_code: int
    payload: JSONDict | None = None
    error_type: str | None = None
    error_message: str | None = None
    extra: JSONDict | None = None


def accepted_plugin_action_response(payload: JSONDict) -> PluginActionResponse:
    return PluginActionResponse(
        success=True,
        status_code=202,
        payload=payload,
    )


def insufficient_disk_space_response(
    exception: InsufficientDiskSpaceError,
) -> PluginActionResponse:
    return PluginActionResponse(
        success=False,
        status_code=exception.http_status,
        error_type=str(exception.code),
        error_message=str(exception.message),
        extra=dict(exception.details or {}),
    )


def network_policy_violation_response(exception: Exception) -> PluginActionResponse:
    return PluginActionResponse(
        success=False,
        status_code=403,
        error_type="network_policy_violation",
        error_message=str(exception),
    )
