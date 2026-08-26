"""SoAI - Plugin download request and target path validation [backend/plugins/state/download_request_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import ParseResult, urlparse

from core.errors.exceptions import ValidationError
from core.network.policy import enforce_url_network_policy
from core.runtime.network_policy import (
    get_dns_validation_timeout_sec,
    is_block_private_network_egress_enabled,
)
from core.types.json import is_json_value
from plugins.action_response import (
    PluginActionResponse,
    network_policy_violation_response,
)
from plugins.path_safety import normalize_plugin_filename
from plugins.responses import build_invalid_filename_response
from plugins.state.download_online_mode import require_plugin_download_online_mode

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginDownloadManagerProtocol,
    )

__all__ = (
    "PluginDownloadPreparation",
    "build_download_metadata",
    "prepare_plugin_download",
)


@dataclass(frozen=True, slots=True)
class PluginDownloadPreparation:
    url: str
    parsed_url: ParseResult
    filename: str
    plugin_name: str
    final_path: str
    network_policy_enabled: bool
    dns_timeout_sec: float
    allow_insecure_downloads: bool


async def prepare_plugin_download(
    manager: PluginDownloadManagerProtocol,
    url: str,
    *,
    enforce_initial_network_policy: bool,
) -> PluginDownloadPreparation | PluginActionResponse:
    parsed_url = urlparse(url)
    scheme = parsed_url.scheme.lower()
    if scheme not in {"http", "https"}:
        return PluginActionResponse(
            success=False,
            status_code=400,
            error_type="invalid_url",
            error_message="Only HTTP(S) URLs are supported for plugin downloads.",
        )
    if scheme != "https" and (not manager.state.configuration.allow_insecure_downloads):
        return PluginActionResponse(
            success=False,
            status_code=400,
            error_type="insecure_url",
            error_message="Plugin downloads must use HTTPS. Set PLUGINS.SECURITY.ALLOW_INSECURE_DOWNLOADS to true to override.",
        )
    if not parsed_url.netloc:
        return PluginActionResponse(
            success=False,
            status_code=400,
            error_type="invalid_url",
            error_message="Plugin download URL must include a hostname.",
        )
    try:
        hostname = parsed_url.hostname
        _ = parsed_url.port
    except ValueError as exception:
        return PluginActionResponse(
            success=False,
            status_code=400,
            error_type="invalid_url",
            error_message=f"Plugin download URL is invalid: {exception}",
        )
    if not hostname or not hostname.strip():
        return PluginActionResponse(
            success=False,
            status_code=400,
            error_type="invalid_url",
            error_message="Plugin download URL must include a hostname.",
        )
    runtime_flags = manager.dependencies.infrastructure.runtime_flags
    offline_error = require_plugin_download_online_mode(runtime_flags)
    if offline_error is not None:
        return offline_error
    network_policy_enabled = is_block_private_network_egress_enabled(runtime_flags)
    dns_timeout_sec = get_dns_validation_timeout_sec(runtime_flags)
    if enforce_initial_network_policy:
        try:
            await enforce_url_network_policy(
                url,
                block_private_networks=network_policy_enabled,
                dns_timeout_sec=dns_timeout_sec,
                source="plugin_download",
            )
        except ValidationError as exception:
            return network_policy_violation_response(exception)
    filename = parsed_url.path.rsplit("/", 1)[-1]
    try:
        plugin_name, final_path = normalize_plugin_filename(manager, filename)
    except (ValueError, ValidationError) as exception:
        return build_invalid_filename_response(exception)
    return PluginDownloadPreparation(
        url=url,
        parsed_url=parsed_url,
        filename=filename,
        plugin_name=plugin_name,
        final_path=final_path,
        network_policy_enabled=network_policy_enabled,
        dns_timeout_sec=dns_timeout_sec,
        allow_insecure_downloads=manager.state.configuration.allow_insecure_downloads,
    )


def build_download_metadata(filename: str, plugin_name: str) -> JSONDict:
    metadata: JSONDict = {}
    for key, value in {"filename": filename, "plugin": plugin_name}.items():
        if is_json_value(value):
            metadata[key] = value
    return metadata
