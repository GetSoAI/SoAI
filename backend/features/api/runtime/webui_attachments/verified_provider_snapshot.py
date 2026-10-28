"""SoAI - Verified provider descriptor snapshots [backend/features/api/runtime/webui_attachments/verified_provider_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_after
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from features.api.runtime.webui_attachments.physical_file_snapshot import (
    open_verified_soai_file_descriptor,
)
from features.api.runtime.webui_attachments.provider_descriptor_snapshot import (
    close_provider_descriptor_snapshot,
    load_provider_descriptor_snapshot,
)

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.files.database_types import FileCatalogRecordWithPath
    from core.types.json import JSONDict
    from features.api.runtime.webui_attachments.provider_descriptor_snapshot import (
        ProviderDescriptorSnapshot,
    )

__all__ = ("load_verified_provider_descriptor_snapshot",)


async def load_verified_provider_descriptor_snapshot(
    storage_root: str,
    *,
    file_content_pool: BoundedBlockingPool,
    record: FileCatalogRecordWithPath,
    attachment: JSONDict,
) -> ProviderDescriptorSnapshot | None:
    managed = await open_verified_soai_file_descriptor(
        storage_root,
        file_content_pool=file_content_pool,
        record=record,
        attachment=attachment,
    )
    try:
        deadline = deadline_after(float(INTERACTIVE_TIMEOUT_SEC))
        snapshot_loader = partial(
            load_provider_descriptor_snapshot,
            deadline=deadline,
            source_descriptor=managed.descriptor,
            filename=str(attachment.get("filename") or ""),
            expected_size_bytes=record["size_bytes"],
            expected_sha256=record["content_sha256"],
        )
        return await run_joined_thread_call(
            snapshot_loader,
            admission_deadline=deadline,
            task_name="webui-attachment-provider-snapshot",
            pool=file_content_pool,
            retain_resources_until_complete=True,
            cancelled_result_cleanup=close_provider_descriptor_snapshot,
        )
    finally:
        os.close(managed.descriptor)
