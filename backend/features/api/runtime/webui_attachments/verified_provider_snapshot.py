"""SoAI - Verified provider descriptor snapshots [backend/features/api/runtime/webui_attachments/verified_provider_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from features.api.runtime.webui_attachments.physical_file_snapshot import (
    open_verified_soai_file_descriptor,
)
from features.api.runtime.webui_attachments.provider_descriptor_snapshot import (
    close_provider_descriptor_snapshot,
    load_provider_descriptor_snapshot,
)

if TYPE_CHECKING:
    from core.files.database_types import FileCatalogRecordWithPath
    from core.types.json import JSONDict
    from features.api.runtime.webui_attachments.provider_descriptor_snapshot import (
        ProviderDescriptorSnapshot,
    )

__all__ = ("load_verified_provider_descriptor_snapshot",)


def _close_cancelled_snapshot(snapshot: ProviderDescriptorSnapshot | None) -> None:
    if snapshot is not None:
        close_provider_descriptor_snapshot(snapshot)


async def load_verified_provider_descriptor_snapshot(
    storage_root: str,
    *,
    record: FileCatalogRecordWithPath,
    attachment: JSONDict,
) -> ProviderDescriptorSnapshot | None:
    managed = await open_verified_soai_file_descriptor(
        storage_root,
        record=record,
        attachment=attachment,
    )
    try:
        snapshot_loader = partial(
            load_provider_descriptor_snapshot,
            source_descriptor=managed.descriptor,
            filename=str(attachment.get("filename") or ""),
            expected_size_bytes=record["size_bytes"],
            expected_sha256=record["content_sha256"],
        )
        return await run_joined_thread_call(
            snapshot_loader,
            task_name="webui-attachment-provider-snapshot",
            cancelled_result_cleanup=_close_cancelled_snapshot,
        )
    finally:
        os.close(managed.descriptor)
