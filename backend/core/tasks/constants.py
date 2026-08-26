"""SoAI - Task constants for plugin system [backend/core/tasks/constants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.tasks.type_catalog import (
    TASK_TYPE_BACKEND_INSTALL,
    TASK_TYPE_BACKEND_REMOVE,
    TASK_TYPE_BACKEND_UPDATE,
    TASK_TYPE_BACKEND_UPDATE_ALL,
    TASK_TYPE_FORCE_CLEANUP,
    TASK_TYPE_MODEL_DOWNLOAD,
    TASK_TYPE_PLUGIN_CLONE,
    TASK_TYPE_PLUGIN_DELETE,
    TASK_TYPE_PLUGIN_DOWNLOAD,
    TASK_TYPE_PLUGIN_UPLOAD,
    TaskTypeId,
)

__all__ = ()

PLUGIN_TASK_TTL_MS: int = 604_800_000
MUTATION_MAX_ATTEMPTS: int = 5

PLUGIN_TASK_TYPE_PAIRS: tuple[tuple[str, TaskTypeId], ...] = (
    ("model_download", TASK_TYPE_MODEL_DOWNLOAD),
    ("install_backend", TASK_TYPE_BACKEND_INSTALL),
    ("update_backend", TASK_TYPE_BACKEND_UPDATE),
    ("update_all_backends", TASK_TYPE_BACKEND_UPDATE_ALL),
    ("remove_backend", TASK_TYPE_BACKEND_REMOVE),
    ("clone_plugin", TASK_TYPE_PLUGIN_CLONE),
    ("delete_plugin", TASK_TYPE_PLUGIN_DELETE),
    ("upload_plugin", TASK_TYPE_PLUGIN_UPLOAD),
    ("download_plugin", TASK_TYPE_PLUGIN_DOWNLOAD),
    ("force_cleanup", TASK_TYPE_FORCE_CLEANUP),
)
