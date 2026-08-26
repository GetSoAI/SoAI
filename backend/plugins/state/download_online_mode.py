"""SoAI - Plugin download online-mode enforcement [backend/plugins/state/download_online_mode.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.runtime.network_policy import OfflineModeError, require_online_mode
from core.runtime.protocols import RuntimeFlagsViewProtocol
from plugins.action_response import PluginActionResponse

__all__ = (
    "build_plugin_download_offline_mode_response",
    "require_plugin_download_online_mode",
)


def build_plugin_download_offline_mode_response(
    exception: OfflineModeError,
) -> PluginActionResponse:
    return PluginActionResponse(
        success=False,
        status_code=403,
        error_type="offline_mode",
        error_message=str(exception),
    )


def require_plugin_download_online_mode(
    runtime_flags: RuntimeFlagsViewProtocol,
) -> PluginActionResponse | None:
    try:
        require_online_mode(runtime_flags, source="plugin_download")
    except OfflineModeError as exception:
        return build_plugin_download_offline_mode_response(exception)
    return None
