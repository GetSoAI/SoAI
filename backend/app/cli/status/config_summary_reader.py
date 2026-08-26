"""SoAI - CLI status config summary reader [backend/app/cli/status/config_summary_reader.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.cli.offline_mode import resolve_config_path
from app.cli.status.types import ConfigSummary
from app.config.io import ConfigIO, ConfigIODependencies
from core.config.summary_fields import (
    coerce_summary_bool,
    coerce_summary_int,
    coerce_summary_mapping,
)
from core.config.value_validation import is_config_dict
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.open_files import open_text
from core.logging.trace import get_logger
from core.validation.strings import coerce_optional_trimmed_str

__all__ = ("read_config_summary_quick",)

LOGGER_NAME = "SoAI.app.cli.config_summary_reader"
OPERATION_APP_CLI_STATUS_READ_CONFIG_SUMMARY_QUICK = "app.cli.status.read_config_summary_quick"
OPERATION_APP_CLI_STATUS_READ_CONFIG_SUMMARY_QUICK_PARSE = (
    "app.cli.status.read_config_summary_quick.parse"
)


def read_config_summary_quick(base_dir: str) -> ConfigSummary | None:
    config_path = resolve_config_path(base_dir)
    try:
        with open_text(config_path, encoding="utf-8") as handle:
            raw_contents = handle.read()
    except OSError as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to read config.yaml for status output (non-critical).",
            operation=OPERATION_APP_CLI_STATUS_READ_CONFIG_SUMMARY_QUICK,
            level="debug",
        )
        return None

    if not raw_contents.strip():
        return None

    config_io = ConfigIO(
        ConfigIODependencies(
            base_path=base_dir,
            core_config_path=config_path,
            plugins_path=None,
            lock_directory=None,
            logger=get_logger(LOGGER_NAME),
        ),
    )
    try:
        parsed = config_io.parse_config_contents(
            raw_contents,
            config_name="core",
            config_path=config_path,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to parse config.yaml for status output (non-critical).",
            operation=OPERATION_APP_CLI_STATUS_READ_CONFIG_SUMMARY_QUICK_PARSE,
            level="debug",
        )
        return None

    if not is_config_dict(parsed):
        return None

    core_value = coerce_summary_mapping(parsed.get("SYSTEM"))
    runtime_value = (
        coerce_summary_mapping(core_value.get("RUNTIME")) if core_value is not None else None
    )
    stay_offline = (
        coerce_summary_bool(runtime_value.get("STAY_OFFLINE"))
        if runtime_value is not None
        else None
    )

    system_api_host: str | None = None
    system_api_port: int | None = None
    system_api_tls_enabled: bool | None = None
    system_api_discovery_host: str | None = None

    server_value = coerce_summary_mapping(parsed.get("SERVER"))
    system_api_value = (
        coerce_summary_mapping(server_value.get("HTTP")) if server_value is not None else None
    )
    if system_api_value is not None:
        network_value = coerce_summary_mapping(system_api_value.get("NETWORK"))
        if network_value is not None:
            system_api_host = coerce_optional_trimmed_str(network_value.get("HOST"))
            system_api_port = coerce_summary_int(network_value.get("PORT"))
            system_api_discovery_host = coerce_optional_trimmed_str(
                network_value.get("DISCOVERY_HOST"),
            )
        ssl_value = coerce_summary_mapping(system_api_value.get("SSL"))
        if ssl_value is not None:
            system_api_tls_enabled = coerce_summary_bool(ssl_value.get("TLS_ENABLED"))

    webui_enabled: bool | None = None
    webui_host: str | None = None
    webui_path: str | None = None
    webui_auto_open_browser: bool | None = None

    webui_value = (
        coerce_summary_mapping(server_value.get("WEBUI")) if server_value is not None else None
    )
    if webui_value is not None:
        webui_enabled = coerce_summary_bool(webui_value.get("ENABLED"))
        webui_host = coerce_optional_trimmed_str(webui_value.get("HOST"))
        webui_path = coerce_optional_trimmed_str(webui_value.get("PATH"))
        webui_auto_open_browser = coerce_summary_bool(webui_value.get("AUTO_OPEN_BROWSER"))

    return ConfigSummary(
        stay_offline=stay_offline,
        system_api_host=system_api_host,
        system_api_port=system_api_port,
        system_api_tls_enabled=system_api_tls_enabled,
        system_api_discovery_host=system_api_discovery_host,
        webui_enabled=webui_enabled,
        webui_host=webui_host,
        webui_path=webui_path,
        webui_auto_open_browser=webui_auto_open_browser,
    )
