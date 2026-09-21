"""SoAI - Read-only WebUI message attachment projection [backend/features/api/runtime/webui_attachments/message_read_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.attachments.attachment_content_parts import content_part_from_unavailable_file
from core.attachments.attachment_content_validation import validate_soai_file_content_part
from core.errors.exceptions import ValidationError
from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.storage_root_resolution import resolve_managed_files_storage_root
from core.types.json_value import copy_json_dict
from features.api.runtime.webui_attachments.physical_file_snapshot import (
    load_soai_file_attachment,
    load_soai_file_record,
    open_verified_soai_file_descriptor,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("project_message_attachments_for_read",)


async def project_message_attachments_for_read(
    *,
    dependencies: ApiDependencies,
    conv_id: str,
    user_id: int,
    messages: Sequence[JSONDict],
) -> list[JSONDict]:
    projected_messages = [copy_json_dict(message) for message in messages]
    storage_root: str | None = None
    for message in projected_messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        if message.get("role") != "user":
            if any(isinstance(part, dict) and part.get("type") == "soai_file" for part in content):
                raise ValidationError("SoAI file content parts are only valid in user messages.")
            continue
        for part_index, part_value in enumerate(content):
            if not isinstance(part_value, dict) or part_value.get("type") != "soai_file":
                continue
            canonical_part = validate_soai_file_content_part(part_value)
            attachment = await load_soai_file_attachment(
                dependencies.database_conversation_attachments,
                conv_id=conv_id,
                user_id=user_id,
                part=canonical_part,
            )
            if attachment is None:
                content[part_index] = content_part_from_unavailable_file(canonical_part)
                continue
            file_record = await load_soai_file_record(
                dependencies.database_files,
                user_id=user_id,
                attachment=attachment,
            )
            if file_record is None:
                content[part_index] = content_part_from_unavailable_file(canonical_part)
                continue
            if storage_root is None:
                storage_root = resolve_managed_files_storage_root(
                    dependencies.config,
                    dependencies.files,
                )
            try:
                managed = await open_verified_soai_file_descriptor(
                    storage_root,
                    record=file_record,
                    attachment=attachment,
                )
            except FileStorageSecurityError:
                content[part_index] = content_part_from_unavailable_file(canonical_part)
                continue
            os.close(managed.descriptor)
    return projected_messages
