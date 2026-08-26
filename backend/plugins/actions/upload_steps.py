"""SoAI - Plugin upload validation move and load steps [backend/plugins/actions/upload_steps.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.events.types_system import TriggerConfigReconciliationCommand
from core.files.move_with_cancellation import move_file_with_cancellation
from core.hardware.reservation_claims import claim_reserved_write
from plugins.actions.upload_validation import (
    load_and_validate_uploaded_plugin,
    validate_upload_destination_available,
)
from plugins.package_audit import audit_plugin_package

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.runtime.request_context import RequestContext
    from plugins.actions.upload_cleanup import UploadExecutionState
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )
    from plugins.protocols_internal.task_progress.internal_protocols import (
        TaskProgressSenderProtocol,
    )

__all__ = ("perform_plugin_upload_steps",)


async def perform_plugin_upload_steps(
    manager: PluginManagerRuntimeProtocol,
    *,
    progress: TaskProgressSenderProtocol,
    task_token: CancellationTokenProtocol,
    state: UploadExecutionState,
    plugin_name: str,
    final_path: str,
    temp_file_path: str,
    context: RequestContext | None,
) -> bool:
    await progress(5, f"Starting plugin upload for '{plugin_name}'...")
    await validate_upload_destination_available(manager, plugin_name, final_path)
    await progress(15, "Validating plugin package...")
    await audit_plugin_package(
        manager,
        plugin_name,
        file_path_override=temp_file_path,
        enforce_import_scan=True,
        enforce_hash_policy=True,
    )
    state.placeholder_created = (
        await manager.dependencies.databases.plugins.create_uploading_placeholder(plugin_name)
    )
    await progress(30, "Moving plugin file to plugins directory...")
    upload_size = int(os.stat(temp_file_path).st_size)
    with manager.dependencies.infrastructure.storage_manager.reserve_disk_space(
        path=final_path,
        required_bytes=upload_size,
        operation="plugin_flow.process_upload_plugin_async.install",
        details={
            "purpose": "plugin_upload_install_volume",
            "plugin_name": plugin_name,
            "final_path": final_path,
            "upload_size_bytes": upload_size,
        },
    ) as install_reservation:
        with claim_reserved_write(install_reservation, size_bytes=upload_size):
            await move_file_with_cancellation(temp_file_path, final_path, task_token)
    state.file_moved = True
    await progress(50, "Loading plugin...")
    await progress(70, "Checking compatibility...")
    requires_backend_install = await load_and_validate_uploaded_plugin(
        manager,
        plugin_name=plugin_name,
        final_path=final_path,
    )
    state.plugin_loaded = True
    await progress(85, "Finalizing configuration...")
    await manager.dependencies.infrastructure.event_bus.publish(
        TriggerConfigReconciliationCommand(
            reason=f"plugin_uploaded:{plugin_name}", context=context
        ),
    )
    await progress(100, "Upload complete.")
    return requires_backend_install
