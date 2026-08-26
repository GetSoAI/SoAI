"""SoAI - Persistent plugin runtime truth helpers [backend/core/plugins/persistent_runtime_truth.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ServiceUnavailableError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.state.state_names import (
    ORCH_STATE_ERROR,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_PERSISTENT_READY,
)
from core.validation.boolean_coercion import coerce_payload_bool

if TYPE_CHECKING:
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.state.state_names import PluginRuntimeStateName
    from core.types.json import JSONDict

__all__ = (
    "get_plugin_status_payload",
    "plugin_status_reports_installed",
    "resolve_persistent_runtime_state",
)

OPERATION_CORE_PLUGINS_PERSISTENT_RUNTIME_TRUTH_ATTEMPT_PLUGIN_START = (
    "core.plugins.persistent_runtime_truth.attempt_plugin_start"
)
OPERATION_CORE_PLUGINS_PERSISTENT_RUNTIME_TRUTH_CHECK_PLUGIN_HEALTH = (
    "core.plugins.persistent_runtime_truth.check_plugin_health"
)
OPERATION_CORE_PLUGINS_PERSISTENT_RUNTIME_TRUTH_GET_PLUGIN_STATUS_PAYLOAD = (
    "core.plugins.persistent_runtime_truth.get_plugin_status_payload"
)
OPERATION_CORE_PLUGINS_PERSISTENT_RUNTIME_TRUTH_RESOLVE_PERSISTENT_RUNTIME_STATE = (
    "core.plugins.persistent_runtime_truth.resolve_persistent_runtime_state"
)


async def get_plugin_status_payload(
    instance: PluginInstanceProtocol,
    *,
    operation: str,
    logger: LoggerProtocol,
    raise_on_error: bool = False,
) -> JSONDict:
    try:
        status = await instance.get_status()
    except RECOVERABLE_EXCEPTIONS as exception:
        if raise_on_error:
            raise
        log_exception(
            logger,
            exception,
            message="Failed to query plugin status.",
            operation=OPERATION_CORE_PLUGINS_PERSISTENT_RUNTIME_TRUTH_GET_PLUGIN_STATUS_PAYLOAD,
            details={"plugin_name": instance.plugin_name, "operation": operation},
            level="warning",
        )
        return {}
    if isinstance(status, dict):
        return status
    if raise_on_error:
        raise ServiceUnavailableError(
            "Plugin status response is unavailable.",
            operation=operation,
        )
    return {}


def plugin_status_reports_installed(
    status_payload: JSONDict,
    *,
    operation: str,
    logger: LoggerProtocol,
    default: bool,
) -> bool:
    return coerce_payload_bool(
        status_payload.get("installed"),
        logger=logger,
        operation=operation,
        default=default,
    )


async def _check_plugin_health(
    instance: PluginInstanceProtocol,
    *,
    operation: str,
    logger: LoggerProtocol,
) -> tuple[bool, str]:
    try:
        is_healthy, message = await instance.health_ping()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Persistent plugin health validation failed.",
            operation=OPERATION_CORE_PLUGINS_PERSISTENT_RUNTIME_TRUTH_CHECK_PLUGIN_HEALTH,
            details={"plugin_name": instance.plugin_name, "operation": operation},
            level="warning",
        )
        return (False, "Persistent backend health is unavailable.")
    return (bool(is_healthy), str(message or ""))


async def _attempt_plugin_start(
    instance: PluginInstanceProtocol,
    *,
    operation: str,
    logger: LoggerProtocol,
) -> bool:
    try:
        start_result = instance.start()
        if inspect.isawaitable(start_result):
            return bool(await start_result)
        return bool(start_result)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Persistent plugin start attempt failed.",
            operation=OPERATION_CORE_PLUGINS_PERSISTENT_RUNTIME_TRUTH_ATTEMPT_PLUGIN_START,
            details={"plugin_name": instance.plugin_name, "operation": operation},
            level="warning",
        )
        return False


async def resolve_persistent_runtime_state(
    instance: PluginInstanceProtocol,
    *,
    attempt_activate: bool,
    failure_state: PluginRuntimeStateName = ORCH_STATE_ERROR,
    operation: str,
    logger: LoggerProtocol,
    status_payload: JSONDict | None = None,
) -> tuple[PluginRuntimeStateName, str, JSONDict]:
    if status_payload is not None:
        resolved_status_payload = dict(status_payload)
    else:
        try:
            resolved_status_payload = await get_plugin_status_payload(
                instance,
                operation=f"{operation}.get_status",
                logger=logger,
                raise_on_error=True,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Persistent plugin status resolution failed.",
                operation=OPERATION_CORE_PLUGINS_PERSISTENT_RUNTIME_TRUTH_RESOLVE_PERSISTENT_RUNTIME_STATE,
                details={"plugin_name": instance.plugin_name, "operation": operation},
                level="warning",
            )
            return (
                failure_state,
                "Persistent backend status is unavailable.",
                {},
            )
    if not plugin_status_reports_installed(
        resolved_status_payload,
        operation=f"{operation}.installed",
        logger=logger,
        default=(not instance.SUPPORTS_BACKEND_INSTALLATION),
    ):
        return (
            PLUGIN_STATE_BACKEND_NOT_INSTALLED,
            "Persistent backend is not installed.",
            resolved_status_payload,
        )
    is_healthy, _health_message = await _check_plugin_health(
        instance,
        operation=f"{operation}.health_ping",
        logger=logger,
    )
    if is_healthy:
        return (
            PLUGIN_STATE_PERSISTENT_READY,
            "Persistent backend is healthy.",
            resolved_status_payload,
        )
    if attempt_activate and await _attempt_plugin_start(
        instance,
        operation=f"{operation}.start",
        logger=logger,
    ):
        resolved_status_payload = await get_plugin_status_payload(
            instance,
            operation=f"{operation}.post_start_status",
            logger=logger,
        )
        is_healthy, _health_message = await _check_plugin_health(
            instance,
            operation=f"{operation}.post_start_health_ping",
            logger=logger,
        )
        if is_healthy:
            return (
                PLUGIN_STATE_PERSISTENT_READY,
                "Persistent backend started and passed health validation.",
                resolved_status_payload,
            )
    return (
        failure_state,
        "Persistent backend failed health validation.",
        resolved_status_payload,
    )
