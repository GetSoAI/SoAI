"""SoAI - Verified provider descriptor snapshots [backend/features/api/runtime/webui_attachments/verified_provider_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from features.api.runtime.webui_attachments.physical_file_snapshot import (
    open_verified_soai_file_descriptor,
)
from features.api.runtime.webui_attachments.provider_descriptor_snapshot import (
    load_provider_descriptor_snapshot,
)

if TYPE_CHECKING:
    from core.files.database_types import FileCatalogRecordWithPath
    from core.types.json import JSONDict
    from features.api.runtime.webui_attachments.projection_context import (
        WebuiAttachmentProjectionContext,
    )
    from features.api.runtime.webui_attachments.provider_descriptor_snapshot import (
        ProviderDescriptorSnapshot,
    )

__all__ = ("load_verified_provider_descriptor_snapshot",)


async def load_verified_provider_descriptor_snapshot(
    context: WebuiAttachmentProjectionContext,
    *,
    record: FileCatalogRecordWithPath,
    attachment: JSONDict,
) -> ProviderDescriptorSnapshot | None:
    source_descriptor = await open_verified_soai_file_descriptor(
        context,
        record=record,
        attachment=attachment,
    )
    try:
        return await asyncio.to_thread(
            load_provider_descriptor_snapshot,
            source_descriptor=source_descriptor,
            filename=str(attachment.get("filename") or ""),
            expected_size_bytes=record["size_bytes"],
            expected_sha256=record["content_sha256"],
        )
    finally:
        os.close(source_descriptor)
