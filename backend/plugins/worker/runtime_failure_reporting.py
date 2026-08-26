"""SoAI - Plugin-managed runtime failure reporting [backend/plugins/worker/runtime_failure_reporting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.concurrency.context import create_system_cancellation_id
from core.errors.exceptions import StateError, ValidationError
from core.logging.trace import get_logger
from core.plugins.name_validation import require_plugin_name
from core.types.json import JSONDict
from core.validation.identifiers import validate_safe_identifier
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.worker.controller_faults import mark_managed_runtime_failed

__all__ = (
    "WorkerRuntimeFailureReporter",
    "report_managed_runtime_failure",
)

RUNTIME_COMPONENT_PATTERN = r"[a-z0-9](?:[a-z0-9_.-]{0,63})"
RUNTIME_FAILURE_CODE_PATTERN = r"[a-z0-9](?:[a-z0-9_.-]{0,63})"
LOGGER_NAME = "SoAI.plugins.worker.runtime_failure_reporting"


class WorkerRuntimeFailureReporter:
    def __init__(
        self,
        request: Callable[[str, JSONDict], Awaitable[JSONDict]],
        *,
        plugin_name: str,
    ) -> None:
        self._request = request
        self._plugin_name = require_plugin_name(plugin_name)

    async def report_runtime_failure(
        self,
        *,
        component: str,
        failure_code: str,
        exit_status: int | None = None,
    ) -> None:
        normalized_component = require_runtime_component(component)
        normalized_failure_code = require_runtime_failure_code(failure_code)
        await self._request(
            "runtime.report_failure",
            {
                "plugin_name": self._plugin_name,
                "component": normalized_component,
                "failure_code": normalized_failure_code,
                "exit_status": exit_status,
            },
        )


async def report_managed_runtime_failure(
    manager: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    component: str,
    failure_code: str,
    exit_status: int | None,
) -> None:
    normalized_plugin_name = require_plugin_name(plugin_name)
    normalized_component = require_runtime_component(component)
    normalized_failure_code = require_runtime_failure_code(failure_code)
    reason = (
        f"Plugin-managed runtime component '{normalized_component}' reported "
        f"terminal failure '{normalized_failure_code}'."
    )
    transitioned = await mark_managed_runtime_failed(
        manager,
        plugin_name=normalized_plugin_name,
        reason=reason,
        exit_status=exit_status,
    )
    if not transitioned:
        return
    orchestrator_lifecycle = manager.orchestrator_lifecycle
    if orchestrator_lifecycle is None:
        raise StateError("Plugin runtime recovery scheduling is unavailable.")
    lifecycle = manager.dependencies.infrastructure.lifecycle
    _ = manager.dependencies.infrastructure.task_helpers.spawn_tracked_task(
        orchestrator_lifecycle.recovery.handle_plugin_recovery(
            normalized_plugin_name,
            reason,
        ),
        name=f"plugin-managed-runtime-recovery-{normalized_plugin_name}",
        logger=get_logger(LOGGER_NAME),
        cancellation_binder=lifecycle.cancellation_binder,
        cancellation_id=create_system_cancellation_id(
            f"plugin_managed_runtime_recovery:{normalized_plugin_name}",
        ),
        owner="plugin_managed_runtime_recovery",
        metadata={"plugin_name": normalized_plugin_name},
        finalizer_tracker=lifecycle.finalizer_tracker,
    )


def require_runtime_component(value: str) -> str:
    normalized = validate_safe_identifier(
        value,
        "component",
        64,
        RUNTIME_COMPONENT_PATTERN,
    )
    if normalized is None:
        raise ValidationError("component is required.")
    return normalized


def require_runtime_failure_code(value: str) -> str:
    normalized = validate_safe_identifier(
        value,
        "failure_code",
        64,
        RUNTIME_FAILURE_CODE_PATTERN,
    )
    if normalized is None:
        raise ValidationError("failure_code is required.")
    return normalized
