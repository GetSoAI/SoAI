"""SoAI - Pre-download validation for model downloads [backend/plugins/actions/model_download_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.events.types_base import Event
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.runtime.network_policy import is_offline_mode_enabled
from plugins.actions.backend_lifecycle_validation import validate_action_for_state_async
from plugins.actions.progress import send_completion_with_task_for_plugin_manager
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "ValidatedDownloadContext",
    "check_offline_mode_blocks_download",
    "validate_plugin_for_download",
)


@dataclass(frozen=True, slots=True)
class ValidatedDownloadContext:
    plugin_instance: PluginInstanceProtocol
    display_name: str


async def check_offline_mode_blocks_download(
    reply_channel: asyncio.Queue[Event],
    task_id: str | None,
    manager: PluginManagerRuntimeProtocol,
) -> bool:
    if not is_offline_mode_enabled(manager.dependencies.infrastructure.runtime_flags):
        return False
    await send_completion_with_task_for_plugin_manager(
        manager,
        reply_channel,
        task_id,
        success=False,
        message="Model downloads are disabled because SYSTEM.RUNTIME.STAY_OFFLINE is enabled.",
    )
    return True


async def validate_plugin_for_download(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    display_name: str,
    reply_channel: asyncio.Queue[Event],
    task_id: str | None,
) -> ValidatedDownloadContext | None:
    if not await validate_action_for_state_async(
        manager,
        plugin_name,
        "download_model",
        reply_channel,
        task_id,
    ):
        return None
    plugin_instance_obj = await manager.require_loaded_plugin(
        plugin_name,
        display_name,
        auto_load=True,
    )
    manager.require_plugin_capability(
        plugin_instance_obj,
        "SUPPORTS_MODEL_DOWNLOAD",
        f"Plugin '{display_name}' is not loaded or does not support model downloads.",
    )
    return ValidatedDownloadContext(
        plugin_instance=plugin_instance_obj,
        display_name=display_name,
    )
