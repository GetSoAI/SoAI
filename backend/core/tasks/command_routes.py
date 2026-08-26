"""SoAI - Explicit task command routing contracts [backend/core/tasks/command_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.events.types_base import Event
from core.events.types_models_model_commands import ModelDownloadCommand
from core.events.types_models_requests import (
    AudioTranscriptionRequestReceived,
    AudioTranslationRequestReceived,
    ImageEditRequestReceived,
    ImageVariationRequestReceived,
)
from core.events.types_plugins import (
    ClonePluginCommand,
    DeletePluginCommand,
    DownloadPluginPackageCommand,
    ForceCleanupPluginCommand,
    InstallPluginBackendCommand,
    RemovePluginBackendCommand,
    UpdateAllPluginBackendsCommand,
    UpdatePluginBackendCommand,
    UploadPluginCommand,
)
from core.tasks.type_catalog import (
    TASK_TYPE_AUDIO_TRANSCRIPTION,
    TASK_TYPE_AUDIO_TRANSLATION,
    TASK_TYPE_BACKEND_INSTALL,
    TASK_TYPE_BACKEND_REMOVE,
    TASK_TYPE_BACKEND_UPDATE,
    TASK_TYPE_BACKEND_UPDATE_ALL,
    TASK_TYPE_FORCE_CLEANUP,
    TASK_TYPE_IMAGE_EDIT,
    TASK_TYPE_IMAGE_VARIATION,
    TASK_TYPE_MODEL_DOWNLOAD,
    TASK_TYPE_PLUGIN_CLONE,
    TASK_TYPE_PLUGIN_DELETE,
    TASK_TYPE_PLUGIN_DOWNLOAD,
    TASK_TYPE_PLUGIN_UPLOAD,
    TaskTypeId,
)

__all__ = ("TaskCommandRoute", "build_base_task_command_routes")


@dataclass(frozen=True, slots=True)
class TaskCommandRoute:
    command_type: type[Event]
    task_type: TaskTypeId


def build_base_task_command_routes() -> tuple[TaskCommandRoute, ...]:
    return (
        TaskCommandRoute(AudioTranscriptionRequestReceived, TASK_TYPE_AUDIO_TRANSCRIPTION),
        TaskCommandRoute(AudioTranslationRequestReceived, TASK_TYPE_AUDIO_TRANSLATION),
        TaskCommandRoute(ImageEditRequestReceived, TASK_TYPE_IMAGE_EDIT),
        TaskCommandRoute(ImageVariationRequestReceived, TASK_TYPE_IMAGE_VARIATION),
        TaskCommandRoute(ModelDownloadCommand, TASK_TYPE_MODEL_DOWNLOAD),
        TaskCommandRoute(InstallPluginBackendCommand, TASK_TYPE_BACKEND_INSTALL),
        TaskCommandRoute(UpdatePluginBackendCommand, TASK_TYPE_BACKEND_UPDATE),
        TaskCommandRoute(UpdateAllPluginBackendsCommand, TASK_TYPE_BACKEND_UPDATE_ALL),
        TaskCommandRoute(RemovePluginBackendCommand, TASK_TYPE_BACKEND_REMOVE),
        TaskCommandRoute(ClonePluginCommand, TASK_TYPE_PLUGIN_CLONE),
        TaskCommandRoute(DeletePluginCommand, TASK_TYPE_PLUGIN_DELETE),
        TaskCommandRoute(DownloadPluginPackageCommand, TASK_TYPE_PLUGIN_DOWNLOAD),
        TaskCommandRoute(UploadPluginCommand, TASK_TYPE_PLUGIN_UPLOAD),
        TaskCommandRoute(ForceCleanupPluginCommand, TASK_TYPE_FORCE_CLEANUP),
    )
