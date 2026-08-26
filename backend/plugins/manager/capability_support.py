"""SoAI - Plugin capability support resolution [backend/plugins/manager/capability_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.types.json import JSONDict
from core.validation.boolean_coercion import coerce_bool_with_recovery
from plugins.manifest.normalized_fields import normalize_supports_external_providers

__all__ = (
    "require_supported_plugin_capability",
    "supports_plugin_capability_from_instance",
    "supports_plugin_capability_from_record",
)

LOGGER_NAME = "SoAI.plugins.manager.capability_support"


def _normalize_capability_key(capability_key: str) -> str:
    return capability_key.strip().upper()


def _read_record_flag(record: JSONDict, key: str) -> bool:
    return coerce_bool_with_recovery(
        record,
        key,
        logger=get_logger(LOGGER_NAME),
        operation="plugins.manager.capability_support.coerce_bool_flag",
        default=False,
        recover_message="Failed to parse plugin capability flag (non-critical).",
    )


def _supports_external_provider_record(record: JSONDict) -> bool:
    provider_mode_value = record.get("external_provider_mode")
    _provider_mode, supports_external = normalize_supports_external_providers(
        provider_mode_value if isinstance(provider_mode_value, str) else None,
        _read_record_flag(record, "supports_external_providers"),
    )
    return supports_external


def supports_plugin_capability_from_instance(
    instance: PluginInstanceProtocol,
    capability_key: str,
) -> bool:
    normalized_key = _normalize_capability_key(capability_key)
    if normalized_key == "SUPPORTS_BACKEND_INSTALLATION":
        return bool(instance.SUPPORTS_BACKEND_INSTALLATION)
    if normalized_key == "SUPPORTS_BACKEND_PROCESS_TRACKING":
        return bool(instance.SUPPORTS_BACKEND_INSTALLATION) and bool(
            instance.SUPPORTS_BACKEND_PROCESS_TRACKING,
        )
    if normalized_key == "SUPPORTS_MODEL_DELETION":
        return bool(instance.SUPPORTS_MODEL_DELETION)
    if normalized_key == "SUPPORTS_MODEL_DOWNLOAD":
        return bool(instance.SUPPORTS_MODEL_DOWNLOAD)
    if normalized_key == "SUPPORTS_MODEL_SEARCH":
        return bool(instance.SUPPORTS_MODEL_SEARCH)
    if normalized_key == "SUPPORTS_CONFIGURATION":
        return bool(instance.SUPPORTS_CONFIGURATION)
    if normalized_key == "SUPPORTS_GPU_BINDING":
        return bool(instance.SUPPORTS_GPU_BINDING)
    if normalized_key == "SUPPORTS_MODEL_VARIANT_DISCOVERY":
        return bool(instance.SUPPORTS_MODEL_VARIANT_DISCOVERY)
    if normalized_key == "SUPPORTS_CLONING":
        return bool(instance.SUPPORTS_CLONING)
    if normalized_key == "SUPPORTS_EXTERNAL_PROVIDERS":
        _provider_mode, supports_external = normalize_supports_external_providers(
            instance.EXTERNAL_PROVIDER_MODE,
            bool(instance.SUPPORTS_EXTERNAL_PROVIDERS),
        )
        return supports_external
    return False


def require_supported_plugin_capability(
    instance: PluginInstanceProtocol,
    capability_name: str,
    failure_message: str,
) -> None:
    capability_key = _normalize_capability_key(capability_name)
    if not capability_key:
        raise ValidationError(failure_message)
    if not supports_plugin_capability_from_instance(instance, capability_key):
        raise ValidationError(failure_message)


def supports_plugin_capability_from_record(
    record: JSONDict,
    capability_key: str,
) -> bool:
    normalized_key = _normalize_capability_key(capability_key)
    if normalized_key == "SUPPORTS_BACKEND_INSTALLATION":
        return _read_record_flag(record, "supports_backend_installation")
    if normalized_key == "SUPPORTS_BACKEND_PROCESS_TRACKING":
        return _read_record_flag(record, "supports_backend_installation") and (
            _read_record_flag(record, "supports_backend_process_tracking")
        )
    if normalized_key == "SUPPORTS_MODEL_DELETION":
        return _read_record_flag(record, "supports_model_deletion")
    if normalized_key == "SUPPORTS_MODEL_DOWNLOAD":
        return _read_record_flag(record, "supports_model_download")
    if normalized_key == "SUPPORTS_MODEL_SEARCH":
        return _read_record_flag(record, "supports_model_search")
    if normalized_key == "SUPPORTS_CONFIGURATION":
        return _read_record_flag(record, "has_configuration")
    if normalized_key == "SUPPORTS_GPU_BINDING":
        return _read_record_flag(record, "supports_gpu_binding")
    if normalized_key == "SUPPORTS_MODEL_VARIANT_DISCOVERY":
        return _read_record_flag(record, "supports_model_variant_discovery")
    if normalized_key == "SUPPORTS_CLONING":
        return _read_record_flag(record, "supports_cloning")
    if normalized_key == "SUPPORTS_EXTERNAL_PROVIDERS":
        return _supports_external_provider_record(record)
    return False
