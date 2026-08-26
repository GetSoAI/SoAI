"""SoAI - WebUI attachment provider projection context [backend/features/api/runtime/webui_attachments/projection_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies
    from features.api.runtime.webui_attachments.provider_projection_session import (
        ProviderAttachmentProjectionSession,
    )
    from features.api.runtime.webui_attachments.provider_video_budget import (
        ProviderVideoAllocation,
    )

__all__ = ("SoaiPathToolAccess", "WebuiAttachmentProjectionContext")


@dataclass(frozen=True, slots=True)
class SoaiPathToolAccess:
    workspace_path: str
    can_read_files: bool
    can_list_folders: bool


@dataclass(frozen=True, slots=True)
class WebuiAttachmentProjectionContext:
    dependencies: ApiDependencies
    conv_id: str
    user_id: int
    vision_supported: bool
    soai_path_tool_access: SoaiPathToolAccess | None
    storage_root: str
    provider_text_char_budget: int
    video_session: ProviderAttachmentProjectionSession
    video_allocations: dict[str, ProviderVideoAllocation]
