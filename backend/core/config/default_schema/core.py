"""SoAI - Default config schema: core settings [backend/core/config/default_schema/core.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.byte_sizes import mib_to_bytes

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_core_defaults",)


def build_core_defaults() -> ConfigDict:
    return {
        "FOUNDATION": {
            "PATHS": {
                "BASE": "",
                "SYSTEM_DATA": "data",
                "SYSTEM_DB": "database/soai.db",
                "TEMP": "temp",
                "FILES_STORAGE": "files",
                "LOCKS": "locks",
                "SYSTEM_ENCRYPTION_KEY": "secret.key",
            },
            "CREDENTIALS": {
                "GITHUB_TOKEN": "",
                "HUGGINGFACE_TOKEN": "",
            },
            "RUNTIME": {
                "STAY_OFFLINE": False,
                "HOST_SYSTEM_ACTIONS_DISABLED": False,
                "HARDWARE_MUTATION_DISABLED": False,
                "STARTUP_BEEP": True,
            },
            "SECURITY": {
                "BLOCK_PRIVATE_NETWORK_EGRESS": False,
                "DNS_VALIDATION_TIMEOUT_SEC": 3.0,
                "DNS_OVERRIDE_SERVERS": "",
            },
            "CONFIG": {
                "POLLING_INTERVAL_MS": 60_000,
            },
            "IPC": {
                "MAX_MESSAGE_BYTES": mib_to_bytes(256),
            },
            "SHUTDOWN": {
                "QUIESCE_PERIOD_SEC": 3,
                "SERVER_DRAIN_TIMEOUT_SEC": 10,
                "COMPONENT_TIMEOUT_SEC": 20,
                "TASK_REGISTRY_TIMEOUT_SEC": 150,
                "ORCHESTRATOR_TIMEOUT_SEC": 75,
                "MCP_TIMEOUT_SEC": 60,
                "FINALIZER_TIMEOUT_SEC": 10,
                "FORCE_CLEANUP_TIMEOUT_SEC": 5,
                "WATCHDOG_TIMEOUT_SEC": 1050,
            },
            "UPDATER": {
                "TIMEOUT_SEC": 10,
                "API_TIMEOUT_SEC": 30,
                "DOWNLOAD_TIMEOUT_SEC": 3600,
                "STREAM_TIMEOUT_SEC": 7200,
                "POST_UPDATE_HOOK_TIMEOUT_SEC": 7200,
                "MAX_ARCHIVE_MB": 2048,
            },
        },
    }
