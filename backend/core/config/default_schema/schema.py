"""SoAI - Code-first default config schema builder [backend/core/config/default_schema/schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.config.default_schema.automation import build_automation_defaults
from core.config.default_schema.backup import build_backup_defaults
from core.config.default_schema.calendar import build_calendar_defaults
from core.config.default_schema.core import build_core_defaults
from core.config.default_schema.database_manager import build_database_manager_defaults
from core.config.default_schema.event_bus import build_event_bus_defaults
from core.config.default_schema.file_explorer import build_file_explorer_defaults
from core.config.default_schema.file_manager import build_file_manager_defaults
from core.config.default_schema.hardware_manager import build_hardware_manager_defaults
from core.config.default_schema.inactivity_monitor import (
    build_inactivity_monitor_defaults,
)
from core.config.default_schema.log_manager import build_log_manager_defaults
from core.config.default_schema.mail import build_mail_defaults
from core.config.default_schema.mcp import build_mcp_defaults
from core.config.default_schema.media_parsing import build_media_parsing_defaults
from core.config.default_schema.metrics_manager import build_metrics_manager_defaults
from core.config.default_schema.model_manager import build_model_manager_defaults
from core.config.default_schema.openai_api import build_openai_api_defaults
from core.config.default_schema.plugin_manager import build_plugin_manager_defaults
from core.config.default_schema.rag import build_rag_defaults
from core.config.default_schema.routing import build_routing_defaults
from core.config.default_schema.system_api import build_system_api_defaults
from core.config.default_schema.task_manager import build_task_manager_defaults
from core.config.default_schema.webui import build_webui_defaults
from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict, ConfigValue

__all__ = ("build_default_config_schema",)


def build_default_config_schema() -> ConfigDict:
    foundation = _require_schema_section(build_core_defaults(), "FOUNDATION")
    schema: ConfigDict = {
        "SYSTEM": _build_system_section(foundation),
        "SERVER": _build_server_section(),
        "API": _build_api_section(),
        "MODELS": _build_models_section(foundation),
        "PLUGINS": _require_schema_section(build_plugin_manager_defaults(), "PLUGINS"),
        "TOOLS": _build_tools_section(),
        "DATA": _build_data_section(foundation),
        "INTEGRATIONS": _build_integrations_section(),
        "AUTOMATION": _require_schema_section(build_automation_defaults(), "AUTOMATION"),
        "OBSERVABILITY": _build_observability_section(),
    }
    _assert_no_null_config_values(schema, prefix="")
    return schema


def _build_system_section(foundation: ConfigDict) -> ConfigDict:
    foundation_paths = _require_mapping(foundation.get("PATHS"), "source foundation PATHS")
    return {
        "PATHS": {
            "BASE": foundation_paths["BASE"],
            "SYSTEM_DATA": foundation_paths["SYSTEM_DATA"],
            "TEMP": foundation_paths["TEMP"],
            "LOCKS": foundation_paths["LOCKS"],
            "SYSTEM_ENCRYPTION_KEY": foundation_paths["SYSTEM_ENCRYPTION_KEY"],
        },
        "RUNTIME": foundation["RUNTIME"],
        "SECURITY": foundation["SECURITY"],
        "CONFIG": foundation["CONFIG"],
        "IPC": foundation["IPC"],
        "SHUTDOWN": foundation["SHUTDOWN"],
        "UPDATER": foundation["UPDATER"],
        "HARDWARE": _require_schema_section(build_hardware_manager_defaults(), "HARDWARE"),
        "TASKS": _require_schema_section(build_task_manager_defaults(), "TASKS"),
        "EVENT_BUS": _require_schema_section(build_event_bus_defaults(), "EVENT_BUS"),
        "INACTIVITY": _require_schema_section(build_inactivity_monitor_defaults(), "INACTIVITY"),
    }


def _build_server_section() -> ConfigDict:
    system_api = build_system_api_defaults()
    return {
        "PUBLIC_ORIGIN": system_api["PUBLIC_ORIGIN"],
        "HTTP": _require_schema_section(system_api, "HTTP"),
        "WEBUI": _require_schema_section(build_webui_defaults(), "WEBUI"),
    }


def _build_api_section() -> ConfigDict:
    return {
        "OPENAI": _require_schema_section(build_openai_api_defaults(), "OPENAI"),
    }


def _build_models_section(foundation: ConfigDict) -> ConfigDict:
    return {
        "CREDENTIALS": foundation["CREDENTIALS"],
        "ROUTING": _require_schema_section(build_routing_defaults(), "ROUTING"),
        "MANAGER": _require_schema_section(build_model_manager_defaults(), "MANAGER"),
    }


def _build_tools_section() -> ConfigDict:
    return {
        "MCP": _require_schema_section(build_mcp_defaults(), "MCP"),
        "MEDIA_PARSING": _require_schema_section(
            build_media_parsing_defaults(),
            "MEDIA_PARSING",
        ),
        "RAG": _require_schema_section(build_rag_defaults(), "RAG"),
    }


def _build_data_section(foundation: ConfigDict) -> ConfigDict:
    foundation_paths = _require_mapping(foundation.get("PATHS"), "source foundation PATHS")
    database_section: ConfigDict = {"PATHS": {"SYSTEM_DB": foundation_paths["SYSTEM_DB"]}}
    database_section.update(_require_schema_section(build_database_manager_defaults(), "DATABASE"))
    files_section: ConfigDict = {"PATHS": {"FILES_STORAGE": foundation_paths["FILES_STORAGE"]}}
    files_section.update(_require_schema_section(build_file_manager_defaults(), "FILES"))
    return {
        "DATABASE": database_section,
        "FILES": files_section,
        "FILE_EXPLORER": _require_schema_section(build_file_explorer_defaults(), "FILE_EXPLORER"),
        "BACKUP": _require_schema_section(build_backup_defaults(), "BACKUP"),
    }


def _build_integrations_section() -> ConfigDict:
    return {
        "MAIL": _require_schema_section(build_mail_defaults(), "MAIL"),
        "CALENDAR": _require_schema_section(build_calendar_defaults(), "CALENDAR"),
    }


def _build_observability_section() -> ConfigDict:
    return {
        "LOGGING": _require_schema_section(build_log_manager_defaults(), "LOGGING"),
        "METRICS": _require_schema_section(build_metrics_manager_defaults(), "METRICS"),
    }


def _require_schema_section(schema: ConfigDict, key: str) -> ConfigDict:
    return _require_mapping(schema.get(key), key)


def _require_mapping(value: ConfigValue | None, key: str) -> ConfigDict:
    if not isinstance(value, dict):
        raise ValidationError(f"Default config section '{key}' must be a mapping.")
    result: ConfigDict = {}
    for item_key, item_value in value.items():
        if not isinstance(item_key, str) or not item_key:
            raise ValidationError(f"Default config section '{key}' contains an invalid key.")
        result[item_key] = item_value
    return result


def _assert_no_null_config_values(value: ConfigValue, *, prefix: str) -> None:
    if value is None:
        raise ValidationError(
            f"Null default value in code-first config schema at: {prefix or '<root>'}",
        )
    if isinstance(value, os.PathLike):
        raise ValidationError(
            f"os.PathLike values are not allowed in the YAML-backed config schema at: {prefix or '<root>'}",
        )
    if isinstance(value, tuple | set | frozenset):
        raise ValidationError(
            f"Non-YAML collection type '{type(value).__name__}' in config schema at: {prefix or '<root>'}",
        )
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str) or not key:
                raise ValidationError(
                    f"Non-string or empty key '{key!r}' in config schema at: {prefix or '<root>'}",
                )
            nested_prefix = f"{prefix}.{key}" if prefix else key
            _assert_no_null_config_values(nested, prefix=nested_prefix)
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            nested_prefix = f"{prefix}[{index}]" if prefix else f"[{index}]"
            _assert_no_null_config_values(nested, prefix=nested_prefix)
        return
