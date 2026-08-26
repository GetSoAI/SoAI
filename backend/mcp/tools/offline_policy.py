"""SoAI - MCP tool offline policy enforcement helpers [backend/mcp/tools/offline_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.network.urls import redact_url_for_logging
from core.runtime.network_policy import (
    OfflineModeError,
    is_offline_mode_enabled,
    validate_local_only_url,
)

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "build_offline_mode_error",
    "is_offline_mode_enabled",
    "require_url_allowed_when_offline",
)


def _build_offline_message(*, tool_name: str, capability: str, url: str | None) -> str:
    prefix = "SYSTEM.RUNTIME.STAY_OFFLINE is enabled."
    if url is None:
        return f"{prefix} {tool_name} cannot access external resources ({capability})."
    return f"{prefix} {tool_name} cannot access external resources ({capability}): {redact_url_for_logging(url)}"


def build_offline_mode_error(
    *,
    tool_name: str,
    capability: str,
    url: str | None,
) -> OfflineModeError:
    return OfflineModeError(
        _build_offline_message(tool_name=tool_name, capability=capability, url=url),
    )


async def require_url_allowed_when_offline(
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    tool_name: str,
    url: str,
    capability: str,
) -> str | None:
    if not is_offline_mode_enabled(runtime_flags):
        return None
    try:
        return await validate_local_only_url(
            runtime_flags,
            url,
            source=capability,
        )
    except ValidationError as exception:
        raise build_offline_mode_error(
            tool_name=tool_name,
            capability=capability,
            url=url,
        ) from exception
    except RECOVERABLE_EXCEPTIONS as exception:
        raise build_offline_mode_error(
            tool_name=tool_name,
            capability=capability,
            url=url,
        ) from exception
