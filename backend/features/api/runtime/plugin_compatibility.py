"""SoAI - API runtime plugin compatibility helpers [backend/features/api/runtime/plugin_compatibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from starlette.requests import Request

from core.plugins.errors import PluginIncompatibleError
from core.plugins.protocols import PluginManagerProtocol
from core.runtime.protocols import RequestProtocol
from features.api.runtime.context import resolve_api_context
from features.api.runtime.errors import raise_conflict, raise_not_found

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ensure_plugin_compatible_or_raise",
    "get_validated_plugin_name",
)


async def get_validated_plugin_name(
    request: Request,
    plugin_name: str,
) -> str:
    api_context = resolve_api_context(request)
    plugin_manager_instance = api_context.dependencies.plugin_manager
    await plugin_manager_instance.require_ready()
    normalized_name = plugin_manager_instance.normalize_plugin_name(plugin_name)
    if not normalized_name:
        raise_not_found(request, f"Plugin '{plugin_name}' not found.")
    return normalized_name


def handle_plugin_incompatible_error(
    request: RequestProtocol,
    exception: PluginIncompatibleError,
) -> NoReturn:
    info = exception.compatibility
    reason_value = info.reason.value if info.reason else None
    payload: JSONDict = {
        "plugin": exception.plugin_name,
        "reason": reason_value,
        "can_override": info.can_override,
        "is_overridden": info.is_overridden,
        "details": info.details,
    }
    message = (
        info.message
        or f"Plugin '{exception.plugin_name}' is incompatible with this SoAI deployment."
    )
    raise_conflict(
        request,
        message,
        error_type="plugin_incompatible",
        extra=payload,
    )


async def ensure_plugin_compatible_or_raise(
    request: RequestProtocol,
    plugin_manager_instance: PluginManagerProtocol,
    plugin_name: str,
) -> None:
    try:
        await plugin_manager_instance.ensure_plugin_compatible(plugin_name)
    except PluginIncompatibleError as error:
        handle_plugin_incompatible_error(request, error)
