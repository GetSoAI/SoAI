"""SoAI - Updater plugin update actions via the SoAI API [backend/app/updater/plugin_update.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ssl
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote

from app.updater.dependencies import PluginUpdateServiceDependencies
from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.plugins.backend_update_results import normalize_backend_update_result
from core.system_api.route_paths import SOAI_ACTIONS_PREFIX, SOAI_TASKS_PREFIX
from core.tasks.identifiers import normalize_optional_task_id
from core.timing.constants import STANDARD_DELAY_SEC
from core.timing.sleep import sleep_seconds

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

    def _collect_plugins_to_update(
        self, updates_info: JSONDict
    ) -> tuple[dict[str, JSONDict], int, int]:
        plugins_to_update: dict[str, JSONDict] = {}
        current_count = 0
        failure_count = 0
        for name, info in updates_info.items():
            result = normalize_backend_update_result(info, installed=True)
            if result.status == "update_available":
                plugins_to_update[name] = result.payload
            elif result.status == "current":
                current_count += 1
            elif result.status == "check_failed":
                error = result.payload.get("error")
                if not isinstance(error, dict) or error.get("code") != "not_implemented":
                    failure_count += 1
        return plugins_to_update, current_count, failure_count

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
        self._logger.info("Plugin backends will be checked and updated sequentially by SoAI.")
        if (not self._args.silent) and input(
            "Proceed with plugin backend checks and updates? (y/n): ",
        ).lower().strip() != "y":
            self._logger.info("Plugin update cancelled by user.")
            return 0
        try:
            base_url, headers, ssl_context = self._api_client.get_base_url_and_auth_headers(
                timeout=self._api_timeout,
            )
            accepted = self._api_client.make_api_request(
                method="POST",
                url=f"{base_url}{SOAI_ACTIONS_PREFIX}/plugins/update-all-backends",
                timeout=self._api_timeout,
                headers=headers,
                ssl_context=ssl_context,
            )
            task_id = normalize_optional_task_id(accepted.get("task_id")) if accepted else None
            if task_id is None:
                self._logger.error(
                    "Backend update batch was not acknowledged with a task identity."
                )
                return 1
            self._logger.info("Backend update batch accepted: %s", task_id)
            deadline = deadline_after(self._stream_timeout)
            previous_message = None
            while not deadline.expired():
                task = self._api_client.make_api_request(
                    method="GET",
                    url=f"{base_url}{SOAI_TASKS_PREFIX}/{quote(task_id, safe='')}",
                    timeout=min(self._api_timeout, deadline.remaining_seconds()),
                    headers=headers,
                    ssl_context=ssl_context,
                )
                if task is None or task.get("task_id") != task_id:
                    self._logger.error(
                        "Backend update task status is unavailable; inspect task %s in SoAI.",
                        task_id,
                    )
                    return 1
                message = task.get("status_message")
                if isinstance(message, str) and message and message != previous_message:
                    self._logger.info("%s", message)
                    previous_message = message
                status = task.get("status")
                if status == "completed":
                    self._logger.info("Backend update batch completed successfully.")
                    return 0
                if status in ("failed", "cancelled"):
                    self._logger.error(
                        "Backend update batch ended with status %s. Inspect task %s in SoAI.",
                        status,
                        task_id,
                    )
                    return 1
                sleep_seconds(min(STANDARD_DELAY_SEC, deadline.remaining_seconds()))
            self._logger.error(
                "Backend update batch has not reached a terminal state. Inspect task %s in SoAI.",
                task_id,
            )
            return 1
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Backend update batch could not complete.",
                operation=OPERATION_APPLICATION_UPDATER_UPDATE_PLUGINS,
            )
            return 1

    def run_plugin_update_check(self) -> int:
        self._logger.info("%s\nChecking for SoAI Plugin Updates\n%s", "=" * 60, "=" * 60)
        context = self._get_plugin_updates_info()
        if context is None:
            return 1
        plugins_to_update, current_count, failure_count = self._collect_plugins_to_update(
            context.updates_info
        )
        if plugins_to_update:
            self._emit_plugin_update_listing(plugins_to_update)
            self._logger.info("Install plugin updates from the SoAI Web UI.")
        if failure_count:
            self._logger.error(
                "%s backend update check(s) failed. Inspect plugin status in SoAI and retry.",
                failure_count,
            )
            return 1
        if not plugins_to_update:
            if current_count:
                self._logger.info("Checked backend installations are up to date.")
            else:
                self._logger.info("No installed backends support update checking.")
        return 0
