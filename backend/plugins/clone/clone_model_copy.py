"""SoAI - Clone model copy task orchestration [backend/plugins/clone/clone_model_copy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_and_wait,
)
from plugins.actions.progress import send_progress_with_task
from plugins.clone_filesystem import copy_model_tree

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("copy_directory_with_progress",)


async def copy_directory_with_progress(
    manager: PluginManagerRuntimeProtocol,
    source: str,
    destination: str,
    reply_channel: asyncio.Queue[Event],
    start_percent: int,
    end_percent: int,
    label: str,
    *,
    task_id: str | None = None,
    aggregate_reservation: DiskSpaceReservationLeaseProtocol | None = None,
    expected_required_bytes: int | None = None,
    expected_source_digest: bytes | None = None,
) -> None:
    await send_progress_with_task(
        reply_channel,
        task_id,
        start_percent,
        f"{label} started.",
        manager.dependencies.infrastructure.task_registry,
    )
    await uncancel_and_wait(
        asyncio.to_thread(
            copy_model_tree,
            source,
            destination,
            manager.dependencies.infrastructure.storage_manager,
            aggregate_reservation,
            expected_required_bytes,
            expected_source_digest,
        )
    )
    if current_task_has_pending_cancellation():
        raise asyncio.CancelledError
    await send_progress_with_task(
        reply_channel,
        task_id,
        end_percent,
        f"{label} complete.",
        manager.dependencies.infrastructure.task_registry,
    )
