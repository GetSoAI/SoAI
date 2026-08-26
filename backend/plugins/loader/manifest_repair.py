"""SoAI - Plugin manifest extraction recovery helpers [backend/plugins/loader/manifest_repair.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.logging.trace import get_logger
from plugins.manifest.reader import read_plugin_manifest_from_disk
from plugins.package_audit import audit_plugin_package

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = (
    "extract_plugin_manifest_with_recovery",
    "recover_plugin_manifest_override",
)

LOGGER_NAME = "SoAI.plugins.loader.manifest_repair"


async def extract_plugin_manifest_with_recovery(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    operation: str,
    error_message: str,
) -> tuple[JSONDict | None, Exception | None]:
    logger = get_logger(LOGGER_NAME)
    try:
        package_audit = await audit_plugin_package(manager, plugin_name)
        manifest = read_plugin_manifest_from_disk(
            manager,
            plugin_name,
            enforce_safety_validation=True,
            package_audit=package_audit,
        )
        return (manifest, None)
    except (OSError, StateError, ValidationError, SyntaxError, TypeError, ValueError) as error:
        soai_error = coerce_to_soai_error(error, operation=operation)
        log_handled_exception(
            logger,
            soai_error,
            message="Plugin manifest could not be read (non-critical).",
            operation=operation,
            level="debug",
            details={"plugin": plugin_name, "error_message": error_message},
        )
        return (None, error)


async def recover_plugin_manifest_override(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    operation: str,
    error_message: str,
) -> tuple[JSONDict | None, Exception | None]:
    plugin_data_override, manifest_error = await extract_plugin_manifest_with_recovery(
        manager,
        plugin_name,
        operation=operation,
        error_message=error_message,
    )
    if plugin_data_override is None:
        return (None, manifest_error)
    if "plugin_name" not in plugin_data_override:
        plugin_data_override["plugin_name"] = plugin_name
    if "name" not in plugin_data_override:
        plugin_data_override["name"] = plugin_name
    return (plugin_data_override, None)
