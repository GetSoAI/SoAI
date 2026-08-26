"""SoAI - Provider projection for WebUI SoAI path attachments [backend/features/api/runtime/webui_attachments/soai_path_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import NotFoundError, SecurityError, ValidationError
from core.files.document_type_detection import extract_extension, is_image_type
from core.workspaces.soai_path_content_validation import validate_soai_path_content_part
from core.workspaces.soai_path_part_fields import (
    source_reference_value,
    target_fingerprint_value,
    tool_reference_value,
    workspace_fingerprint,
)
from core.workspaces.soai_path_resolution import build_soai_path_content_part
from features.api.runtime.webui_attachments.soai_path_file_projection import (
    project_soai_path_file_for_provider,
)
from features.api.runtime.webui_attachments.soai_path_provider_text import (
    build_soai_path_folder_text,
    build_soai_path_reference_text,
    build_soai_path_unavailable_text,
    resolve_optional_soai_path_title,
)
from features.api.runtime.webui_attachments.soai_path_snapshot import (
    load_verified_soai_path_folder_entries,
)
from features.api.runtime.webui_attachments.soai_path_workspace_resolution import (
    resolve_matching_soai_path_workspace,
    soai_path_tool_workspace_matches,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.webui_attachments.projection_context import (
        WebuiAttachmentProjectionContext,
    )

__all__ = ("project_soai_path_for_provider",)


def _is_vision_native_file_part(part: JSONDict) -> bool:
    if part.get("entry_type") != "file":
        return False
    if part.get("preview_type") == "image":
        return True
    if part.get("preview_type") == "video":
        return True
    mime_type = part.get("mime_type")
    title = part.get("title")
    if not isinstance(mime_type, str) or not isinstance(title, str):
        return False
    return is_image_type(mime_type, extract_extension(title))


async def project_soai_path_for_provider(
    context: WebuiAttachmentProjectionContext,
    *,
    part: JSONDict,
) -> list[JSONDict]:
    try:
        stored_part = validate_soai_path_content_part(dict(part))
        stored_fingerprint = workspace_fingerprint(stored_part)
        effective_root = await resolve_matching_soai_path_workspace(
            context,
            stored_fingerprint=stored_fingerprint,
        )
        if effective_root is None:
            return [
                {
                    "type": "text",
                    "text": build_soai_path_unavailable_text(
                        title=resolve_optional_soai_path_title(stored_part),
                        note="Live target unavailable.",
                    ),
                },
            ]
        canonical = build_soai_path_content_part(
            effective_workspace_root=effective_root,
            root_fingerprint=stored_fingerprint,
            conversation_virtual_path=source_reference_value(stored_part),
        )
        if canonical.get("entry_type") != stored_part.get("entry_type"):
            return [
                {
                    "type": "text",
                    "text": build_soai_path_unavailable_text(
                        title=resolve_optional_soai_path_title(stored_part),
                        note="Live target type changed.",
                    ),
                },
            ]
        if target_fingerprint_value(canonical) != target_fingerprint_value(stored_part):
            return [
                {
                    "type": "text",
                    "text": build_soai_path_unavailable_text(
                        title=resolve_optional_soai_path_title(stored_part),
                        note="Live target changed since attachment.",
                    ),
                },
            ]
        if context.vision_supported and _is_vision_native_file_part(canonical):
            return await project_soai_path_file_for_provider(
                context,
                canonical=canonical,
                effective_root=effective_root,
            )
        tool_access = context.soai_path_tool_access
        tool_path_access_allowed = (
            canonical.get("entry_type") == "file"
            and tool_access is not None
            and tool_access.can_read_files
        ) or (
            canonical.get("entry_type") == "folder"
            and tool_access is not None
            and tool_access.can_list_folders
        )
        if (
            tool_access is not None
            and tool_path_access_allowed
            and soai_path_tool_workspace_matches(context, effective_root=effective_root)
        ):
            return [
                {
                    "type": "text",
                    "text": build_soai_path_reference_text(
                        canonical,
                        tool_path=tool_reference_value(canonical),
                    ),
                },
            ]
        if canonical.get("entry_type") == "file":
            return await project_soai_path_file_for_provider(
                context,
                canonical=canonical,
                effective_root=effective_root,
            )
        if canonical.get("entry_type") == "folder":
            entries = load_verified_soai_path_folder_entries(
                effective_root=effective_root,
                canonical=canonical,
            )
            if entries is None:
                return [
                    {
                        "type": "text",
                        "text": build_soai_path_unavailable_text(
                            title=resolve_optional_soai_path_title(stored_part),
                            note="Live target changed since attachment.",
                        ),
                    },
                ]
            return [
                {
                    "type": "text",
                    "text": build_soai_path_folder_text(context, canonical, entries),
                },
            ]
        return [
            {
                "type": "text",
                "text": build_soai_path_reference_text(canonical, note="Live target type changed."),
            },
        ]
    except (NotFoundError, OSError, SecurityError, ValidationError):
        return [
            {
                "type": "text",
                "text": build_soai_path_unavailable_text(
                    title=resolve_optional_soai_path_title(part),
                    note="Live target unavailable.",
                ),
            },
        ]
