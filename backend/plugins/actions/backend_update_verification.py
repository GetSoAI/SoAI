"""SoAI - Local and release verification of backend updates [backend/plugins/actions/backend_update_verification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_exception
from core.errors.exceptions import BackendUpdateContainmentError, SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_plugins import UpdatePluginBackendCommand
from core.plugins.backend_update_results import (
    backend_update_error,
)
from core.plugins.backend_variant_ids import AUTO_BACKEND_VARIANT_ID, require_backend_variant_id
from core.plugins.backend_variant_status import read_installed_backend_variant_id
from core.plugins.persistent_runtime_truth import get_plugin_status_payload
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.timing.constants import EXTENDED_TIMEOUT_SEC
from plugins.actions.backend_update_checkpoints import advance_backend_update
from plugins.actions.progress import send_completion_with_task
from plugins.manager.backend_update_checks import check_instance_backend_update
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = ("complete_backend_update_verification", "validate_updated_backend")

OPERATION = "plugins.actions.backend_update_verification"
VERIFICATION_FAILURES: tuple[type[Exception], ...] = (*RECOVERABLE_EXCEPTIONS, SoAIError)


async def validate_updated_backend(
    manager: PluginManagerRuntimeProtocol,
    command: UpdatePluginBackendCommand,
    instance: PluginInstanceProtocol,
) -> None:
    variant_id = require_backend_variant_id(command.backend_variant_id)
    async with asyncio.timeout(EXTENDED_TIMEOUT_SEC):
        status = await get_plugin_status_payload(
            instance, operation=OPERATION, logger=manager.logger, raise_on_error=True
        )
    if status.get("installed") is not True or status.get("error") is not None:
        raise StateError("Backend update did not produce a verified installation.")
    if (
        variant_id != AUTO_BACKEND_VARIANT_ID
        and read_installed_backend_variant_id(status) != variant_id
    ):
        raise StateError("Backend update did not install the requested variant.")


async def complete_backend_update_verification(
    manager: PluginManagerRuntimeProtocol,
    command: UpdatePluginBackendCommand,
    *,
    task_id: str | None,
    send_completion_event: bool,
) -> bool:
    try:
        instance = await manager.require_loaded_plugin(command.plugin_name, auto_load=True)
        previous = await manager.dependencies.databases.plugins.get_backend_update(
            command.plugin_name
        )
        result = await check_instance_backend_update(
            manager,
            instance,
            previous_check_id=previous.check_id if previous else None,
        )
    except VERIFICATION_FAILURES as exception:
        if isinstance(exception, BackendUpdateContainmentError):
            raise
        log_exception(
            manager.logger,
            exception,
            message="Backend installation completed but release verification failed.",
            operation=OPERATION,
            details={"plugin_name": command.plugin_name},
        )
        result = backend_update_error("verification_failed", "Backend release verification failed.")
    error = result.payload.get("error")
    unsupported = isinstance(error, dict) and error.get("code") == "not_implemented"
    success = result.status in {"current", "update_available"} or unsupported
    message = "Backend update completed and verified."
    if unsupported:
        message = "Backend installation verified; release checking is not supported."
    elif result.status == "update_available":
        message = "Backend update completed; a newer backend release remains available."
    elif not success:
        message = (
            "Backend remains installed, but release verification failed. Retry the update check."
        )
    await advance_backend_update(manager, command, "verified" if success else "contained_failure")
    if send_completion_event:
        await send_completion_with_task(
            command.reply_channel,
            task_id,
            success=success,
            message=message,
            error_message=None if success else message,
            result={"backend_update": result.payload},
            mutation_fencing_token=(
                command.context.mutation_fencing_token if command.context else None
            ),
            task_registry=manager.dependencies.infrastructure.task_registry,
            send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
        )
    return success
