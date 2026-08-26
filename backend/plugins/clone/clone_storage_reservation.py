"""SoAI - Aggregate clone transaction storage capacity [backend/plugins/clone/clone_storage_reservation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_and_wait,
)
from core.config.byte_sizes import MIB_BYTES
from core.hardware.disk_reservation_records import DiskSpaceReservationRequest
from core.plugins.file_suffixes import PLUGIN_FILE_SUFFIX
from core.serialization.json import serialize_json_compact_stable
from plugins.clone.clone_package_plan import inspect_clone_package_source
from plugins.clone.clone_plan import ClonePlan
from plugins.clone.clone_source_manifest import inspect_secure_directory_source

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from core.types.json import JSONDict
    from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = ("CloneStorageReservation", "acquire_clone_storage_reservation")

CONFIG_CAPACITY_HEADROOM_BYTES = MIB_BYTES
TRANSACTION_ROLLBACK_HEADROOM_BYTES = 4 * MIB_BYTES


@dataclass(frozen=True, slots=True)
class CloneStorageReservation:
    lease: DiskSpaceReservationLeaseProtocol
    package_bytes: int
    models_bytes: int
    config_bytes: int
    package_source_digest: bytes
    models_source_digest: bytes | None

    async def release(self) -> None:
        await uncancel_and_wait(asyncio.to_thread(self.lease.release))


def _configuration_capacity_bytes(
    cloned_config: JSONDict,
) -> int:
    serialized_bytes = len(serialize_json_compact_stable(cloned_config).encode("utf-8"))
    return (serialized_bytes * 2) + CONFIG_CAPACITY_HEADROOM_BYTES


async def acquire_clone_storage_reservation(
    manager: PluginManagerRuntimeProtocol,
    plan: ClonePlan,
    cloned_config: JSONDict,
) -> CloneStorageReservation:
    plugin_directory = manager.paths.plugin_directory
    source_plugin_file = os.path.join(
        plugin_directory,
        f"{plan.source_plugin_name}{PLUGIN_FILE_SUFFIX}",
    )
    package_estimate = asyncio.to_thread(
        inspect_clone_package_source,
        source_plugin_file,
        plan.target_plugin_name,
    )
    models_estimate = (
        asyncio.to_thread(inspect_secure_directory_source, plan.source_models_path)
        if plan.clone_models and plan.source_models_path_exists and plan.source_models_path
        else None
    )
    config_bytes = _configuration_capacity_bytes(cloned_config)
    models_source_digest: bytes | None = None
    if models_estimate is None:
        package_snapshot = await package_estimate
        models_bytes = 0
    else:
        package_snapshot, models_snapshot = await asyncio.gather(
            package_estimate,
            models_estimate,
            return_exceptions=False,
        )
        models_bytes = models_snapshot.required_bytes
        models_source_digest = models_snapshot.source_digest
    package_bytes = package_snapshot.required_bytes
    requests = [
        DiskSpaceReservationRequest(
            path=plugin_directory,
            required_bytes=package_bytes,
            operation="plugin_clone.aggregate_package",
        )
    ]
    if models_bytes > 0 and plan.target_models_path:
        requests.append(
            DiskSpaceReservationRequest(
                path=os.path.dirname(plan.target_models_path),
                required_bytes=models_bytes,
                operation="plugin_clone.aggregate_models",
            )
        )
    requests.extend(
        (
            DiskSpaceReservationRequest(
                path=plugin_directory,
                required_bytes=config_bytes,
                operation="plugin_clone.aggregate_configuration",
            ),
            DiskSpaceReservationRequest(
                path=plugin_directory,
                required_bytes=package_bytes
                + models_bytes
                + config_bytes
                + TRANSACTION_ROLLBACK_HEADROOM_BYTES,
                operation="plugin_clone.aggregate_rollback_headroom",
            ),
        )
    )
    lease = await uncancel_and_wait(
        asyncio.to_thread(
            manager.dependencies.infrastructure.storage_manager.reserve_many_disk_spaces,
            requests=requests,
        )
    )
    if current_task_has_pending_cancellation():
        await uncancel_and_wait(asyncio.to_thread(lease.release))
        raise asyncio.CancelledError
    return CloneStorageReservation(
        lease=lease,
        package_bytes=package_bytes,
        models_bytes=models_bytes,
        config_bytes=config_bytes,
        package_source_digest=package_snapshot.source_digest,
        models_source_digest=models_source_digest,
    )
