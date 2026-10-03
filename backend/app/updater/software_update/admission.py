"""SoAI - Software update admission policy [backend/app/updater/software_update/admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.meta.software_update_platforms import supported_update_platforms_for_edition
from core.runtime.platform import get_runtime_platform
from core.runtime.protocols import RuntimeFlagsViewProtocol, RuntimeStateStoreProtocol

__all__ = (
    "UPDATE_IN_PROGRESS_MESSAGE",
    "UPDATE_PLATFORM_UNAVAILABLE_MESSAGE",
    "UPDATE_RESTORE_PENDING_MESSAGE",
    "UPDATE_UNAVAILABLE_MESSAGE",
    "is_update_platform_supported",
    "resolve_update_rejection_message",
)

SELF_UPDATE_DISABLED_MESSAGE = "Self-update is disabled because host system actions are disabled."
UPDATE_IN_PROGRESS_MESSAGE = "Application shutdown or software update is already in progress."
UPDATE_OFFLINE_MESSAGE = (
    "SYSTEM.RUNTIME.STAY_OFFLINE is enabled. Software updates are disabled in offline mode."
)
UPDATE_UNAVAILABLE_MESSAGE = "The software updater is unavailable."
UPDATE_PLATFORM_UNAVAILABLE_MESSAGE = "Automatic software updates do not support this platform."
UPDATE_RESTORE_PENDING_MESSAGE = "A backup restore still requires recovery. Restart the application to complete restore recovery before updating."


def is_update_platform_supported(edition: str) -> bool:
    platform_id = get_runtime_platform().platform_id
    return platform_id in supported_update_platforms_for_edition(edition)


def resolve_update_rejection_message(
    runtime: RuntimeStateStoreProtocol,
    runtime_flags: RuntimeFlagsViewProtocol | None,
) -> str | None:
    if runtime.is_shutting_down or runtime.restart_requested or runtime.system_stop_event.is_set():
        return UPDATE_IN_PROGRESS_MESSAGE
    if runtime_flags is not None and runtime_flags.offline_mode:
        return UPDATE_OFFLINE_MESSAGE
    if runtime_flags is not None and runtime_flags.host_system_actions_disabled:
        return SELF_UPDATE_DISABLED_MESSAGE
    return None
