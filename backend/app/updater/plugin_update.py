"""SoAI - Updater plugin update actions via the SoAI API [backend/app/updater/plugin_update.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ssl
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib import request

from app.updater.dependencies import PluginUpdateServiceDependencies
from app.updater.networking import open_url
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.serialization.json_parsing import parse_json_value
from core.system_api.route_paths import SOAI_ACTIONS_PREFIX
from core.validation.boolean_coercion import coerce_payload_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "PluginUpdateContext",
    "PluginUpdateService",
)

OPERATION_APPLICATION_UPDATER_GET_PLUGIN_UPDATES_INFO = (
    "application_updater.get_plugin_updates_info"
)
OPERATION_APPLICATION_UPDATER_UPDATE_PLUGINS = "application_updater.update_plugins"


@dataclass(frozen=True, slots=True)
class PluginUpdateContext:
    base_url: str
    request_headers: dict[str, str]
    ssl_context: ssl.SSLContext | None
    updates_info: JSONDict


class PluginUpdateService:
    def __init__(self, deps: PluginUpdateServiceDependencies) -> None:
        self._args = deps.args
        self._logger = deps.logger
        self._api_client = deps.api_client
        self._api_timeout = deps.api_timeout
        self._stream_timeout = deps.stream_timeout

    def _get_plugin_updates_info(
        self,
    ) -> PluginUpdateContext | None:
        try:
            base_url, request_headers, ssl_context = self._api_client.get_base_url_and_auth_headers(
                timeout=self._api_timeout,
            )
            self._logger.info("Contacting SoAI API at %s...", base_url)
            updates_info = self._api_client.make_api_request(
                method="POST",
                url=f"{base_url}{SOAI_ACTIONS_PREFIX}/plugins/check-for-updates",
                timeout=self._api_timeout,
                headers=request_headers,
                ssl_context=ssl_context,
            )
            if updates_info is None:
                self._logger.warning(
                    "Failed to get update information. Is the SoAI service running and accessible?",
                )
                return None
            return PluginUpdateContext(
                base_url=base_url,
                request_headers=request_headers,
                ssl_context=ssl_context,
                updates_info=updates_info,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Error connecting to SoAI API. Please ensure SoAI is running and accessible.",
                operation=OPERATION_APPLICATION_UPDATER_GET_PLUGIN_UPDATES_INFO,
            )
            return None

    def _collect_plugins_to_update(self, updates_info: JSONDict) -> dict[str, JSONDict]:
        plugins_to_update: dict[str, JSONDict] = {}
        for name, info in updates_info.items():
            if not isinstance(name, str) or not isinstance(info, dict):
                continue
            if coerce_payload_bool(
                info.get("update_available"),
                logger=self._logger,
                operation="application_updater.plugin_update.coerce_payload_bool",
                default=False,
                recover_message="Failed to parse plugin update payload boolean (non-critical).",
            ):
                plugins_to_update[name] = info
        return plugins_to_update

    def _emit_plugin_update_listing(self, plugins_to_update: dict[str, JSONDict]) -> None:
        self._logger.info("The following plugin updates are available:")
        for name, info in plugins_to_update.items():
            self._logger.info(
                "  - %-10s: %s -> %s",
                name.capitalize(),
                info.get("current_version", "N/A"),
                info.get("latest_version", "N/A"),
            )

    def run_plugin_update(self) -> int:
        self._logger.info("%s\nSoAI Plugin Updater Started\n%s", "=" * 60, "=" * 60)
        context = self._get_plugin_updates_info()
        if context is None:
            return 1
        plugins_to_update = self._collect_plugins_to_update(context.updates_info)
        if not plugins_to_update:
            self._logger.info("All installed plugins are up-to-date.")
            return 0
        self._emit_plugin_update_listing(plugins_to_update)
        if (not self._args.silent) and input(
            "Proceed with plugin updates? (y/n): ",
        ).lower().strip() != "y":
            self._logger.info("Plugin update cancelled by user.")
            return 0
        self._logger.info("Starting plugin update process...")
        try:
            request_obj = request.Request(
                f"{context.base_url}{SOAI_ACTIONS_PREFIX}/plugins/update-all-backends",
                method="POST",
                headers=dict(context.request_headers),
            )
            with open_url(
                request_obj,
                timeout=self._stream_timeout,
                context=context.ssl_context,
                stream=True,
                offline_mode=True,
            ) as response:
                if response.status_code not in (200, 202):
                    self._logger.warning(
                        "API error: %s %s\n%s",
                        response.status_code,
                        response.reason_phrase,
                        response.text,
                    )
                    return 1
                for line in response.iter_lines():
                    line_str = (line or "").strip()
                    if not line_str.startswith("data: "):
                        continue
                    try:
                        data = parse_json_value(line_str[6:])
                        if not isinstance(data, dict):
                            continue
                        plugin_value = data.get("plugin")
                        plugin = plugin_value.strip() if isinstance(plugin_value, str) else ""
                        message = data.get("message", "No message")
                        log_prefix = f"[{plugin.capitalize()}] " if plugin else ""
                        is_error = data.get("type") == "TaskCompleteEvent" and (
                            not coerce_payload_bool(
                                data.get("success"),
                                logger=self._logger,
                                operation="application_updater.plugin_update.coerce_payload_bool",
                                default=False,
                                recover_message="Failed to parse plugin update payload boolean (non-critical).",
                            )
                        )
                        (self._logger.error if is_error else self._logger.info)(
                            "%s%s",
                            log_prefix,
                            message,
                        )
                    except ValidationError:
                        self._logger.info(line_str)
            self._logger.info("Plugin update process finished successfully.")
            return 0
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="An error occurred during the plugin update process.",
                operation=OPERATION_APPLICATION_UPDATER_UPDATE_PLUGINS,
                level="error",
            )
            return 1

    def run_plugin_update_check(self) -> int:
        self._logger.info("%s\nChecking for SoAI Plugin Updates\n%s", "=" * 60, "=" * 60)
        context = self._get_plugin_updates_info()
        if context is None:
            return 1
        plugins_to_update = self._collect_plugins_to_update(context.updates_info)
        if not plugins_to_update:
            self._logger.info("All installed plugins are up-to-date.")
            return 0
        self._emit_plugin_update_listing(plugins_to_update)
        self._logger.info("\nInstall plugin updates from the SoAI Web UI.")
        return 0
