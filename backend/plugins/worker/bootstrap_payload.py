"""SoAI - Parent-side plugin worker bootstrap payload [backend/plugins/worker/bootstrap_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.types.json import JSONDict

__all__ = ("build_plugin_worker_bootstrap_payload", "build_plugin_worker_runtime_flags_payload")


def build_plugin_worker_runtime_flags_payload(
    runtime_flags: RuntimeFlagsViewProtocol,
) -> JSONDict:
    return {
        "host_system_actions_disabled": runtime_flags.host_system_actions_disabled,
        "hardware_mutation_disabled": runtime_flags.hardware_mutation_disabled,
        "offline_mode": runtime_flags.offline_mode,
        "block_private_network_egress": runtime_flags.block_private_network_egress,
        "dns_validation_timeout_sec": runtime_flags.dns_validation_timeout_sec,
        "host_management_available": runtime_flags.host_management_available,
    }


def build_plugin_worker_bootstrap_payload(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    plugin_name: str,
    plugin_package_root: str,
    plugin_entrypoint_path: str,
    plugin_config: JSONDict,
    install_path: str,
) -> JSONDict:
    config_snapshot = _config_snapshot(config)
    return {
        "plugin_name": plugin_name,
        "plugin_package_root": plugin_package_root,
        "plugin_entrypoint_path": plugin_entrypoint_path,
        "plugin_config": dict(plugin_config),
        "install_path": install_path,
        "config_snapshot": config_snapshot,
        "runtime_flags": build_plugin_worker_runtime_flags_payload(runtime_flags),
    }


def _config_snapshot(config: ConfigProtocol) -> JSONDict:
    system_paths = {
        "BASE": config.get_str("SYSTEM.PATHS.BASE"),
        "SYSTEM_DATA": config.get_str("SYSTEM.PATHS.SYSTEM_DATA"),
        "TEMP": config.get_str("SYSTEM.PATHS.TEMP"),
    }
    model_paths = {
        "MODELS": config.get_str("MODELS.MANAGER.PATHS.MODELS"),
    }
    plugin_paths = {
        "PLUGIN_LOGS": config.get_str("PLUGINS.PATHS.PLUGIN_LOGS"),
        "TEMPLATES": config.get_str("PLUGINS.PATHS.TEMPLATES"),
    }
    if not plugin_paths["TEMPLATES"]:
        raise StateError("PLUGINS.PATHS.TEMPLATES must be configured.")
    return {
        "SYSTEM": {"PATHS": system_paths},
        "MODELS": {
            "CREDENTIALS": {
                "GITHUB_TOKEN": config.get_str("MODELS.CREDENTIALS.GITHUB_TOKEN"),
                "HUGGINGFACE_TOKEN": config.get_str("MODELS.CREDENTIALS.HUGGINGFACE_TOKEN"),
            },
            "MANAGER": {"PATHS": model_paths},
        },
        "PLUGINS": {"PATHS": plugin_paths},
    }
