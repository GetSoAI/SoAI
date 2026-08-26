"""SoAI - Turn-scoped attachment projection session [backend/features/api/runtime/webui_attachments/provider_projection_session.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.attachments.attachment_parse_classification import AttachmentParseOutcome
from features.agent.runtime.model_tool_calling import model_supports_vision_input
from features.api.runtime.webui_attachments.provider_video_projection import (
    ProviderVideoProjection,
    project_video_snapshot_for_provider,
)
from features.api.runtime.webui_attachments.provider_video_settings import (
    ProviderVideoSettings,
    read_provider_video_settings,
)

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies
    from features.api.runtime.webui_attachments.provider_video_budget import (
        ProviderVideoAllocation,
    )

__all__ = ("ProviderAttachmentProjectionSession",)


class ProviderAttachmentProjectionSession:
    def __init__(
        self,
        *,
        dependencies: ApiDependencies,
        model_id: str | None,
    ) -> None:
        self.dependencies = dependencies
        self.model_id = model_id
        self.video_settings: ProviderVideoSettings = read_provider_video_settings(
            dependencies.config,
        )
        self._vision_lock = asyncio.Lock()
        self._vision_supported: bool | None = None
        self._video_lock = asyncio.Lock()
        self._video_cache: dict[str, ProviderVideoProjection] = {}
        self._linked_video_parse_lock = asyncio.Lock()
        self._linked_video_parse_cache: dict[str, AttachmentParseOutcome] = {}

    async def vision_supported(self) -> bool:
        async with self._vision_lock:
            if self._vision_supported is not None:
                return self._vision_supported
            supported = (
                False
                if self.model_id is None
                else await model_supports_vision_input(
                    self.dependencies,
                    self.model_id,
                )
            )
            self._vision_supported = supported
            return supported

    async def project_video(
        self,
        *,
        content_identity: str,
        source_path: str,
        allocation: ProviderVideoAllocation,
    ) -> ProviderVideoProjection:
        cache_key = (
            f"{content_identity}:"
            f"{allocation.maximum_frames}:"
            f"{allocation.maximum_encoded_chars}:"
            f"{self.video_settings.signature}"
        )
        async with self._video_lock:
            cached = self._video_cache.get(cache_key)
            if cached is not None:
                return cached.copy()
            projected = await project_video_snapshot_for_provider(
                source_path=source_path,
                allocation=allocation,
                settings=self.video_settings,
                config=self.dependencies.config,
                storage_manager=self.dependencies.storage_manager,
                semaphore=self.dependencies.provider_video_projection_semaphore,
            )
            self._video_cache[cache_key] = projected
            return projected.copy()

    async def classify_linked_video(
        self,
        *,
        content_identity: str,
        classify: Callable[[], Awaitable[AttachmentParseOutcome]],
    ) -> AttachmentParseOutcome:
        async with self._linked_video_parse_lock:
            cached = self._linked_video_parse_cache.get(content_identity)
            if cached is not None:
                return cached
            outcome = await classify()
            self._linked_video_parse_cache[content_identity] = outcome
            return outcome
