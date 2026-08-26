"""SoAI - Plugin state hydration and manifest formatting [backend/plugins/state/hydration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.openai.capabilities import normalize_openai_capabilities
from core.openai.compatibility import ExternalProviderMode
from core.plugins.compatibility_payload import compatibility_to_payload
from core.serialization.json_parsing import parse_json_value
from core.state.circuit_breaker import CircuitBreakerState
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_INCOMPATIBLE,
    PLUGIN_STATE_NOT_DETECTED,
)
from core.types.json import is_json_dict
from core.types.json_value import coerce_str_list
from core.validation.boolean_coercion import coerce_bool_with_recovery
from core.validation.coercion import coerce_non_negative_int_from_numberish
from plugins.manager.compatibility import compatibility_from_record
from plugins.manifest.dependency_snapshot import dependency_snapshot_from_record
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.capability_normalization import as_json_list

if TYPE_CHECKING:
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ()

LOGGER_NAME = "SoAI.plugins.state.hydration"


def _json_load_list(raw_value: JSONValue) -> list[str]:
    if not isinstance(raw_value, str):
        raise ValidationError("Expected JSON list string.")
    try:
        parsed = parse_json_value(raw_value)
    except (ValidationError, TypeError) as exception:
        raise ValidationError(f"Invalid JSON list string: {exception}") from exception
    if not isinstance(parsed, list):
        raise ValidationError("Expected JSON array.")
    parsed_list = coerce_str_list(parsed)
    if parsed_list is None:
        raise ValidationError("Expected JSON array of strings.")
    return parsed_list


def _json_load_dict(raw_value: JSONValue) -> JSONDict:
    if raw_value is None:
        return {}
    if not isinstance(raw_value, str):
        raise ValidationError("Expected JSON object string.")
    try:
        parsed = parse_json_value(raw_value)
    except (ValidationError, TypeError) as exception:
        raise ValidationError(f"Invalid JSON object string: {exception}") from exception
    if not is_json_dict(parsed):
        raise ValidationError("Expected JSON object.")
    return dict(parsed)


def format_plugin_details(
    manager: PluginManagerRuntimeProtocol,
    p_data: JSONDict,
    *,
    instance: PluginInstanceProtocol | None,
    status_payload: JSONDict | None,
    plugin_stats: Mapping[str, Mapping[str, JSONValue]],
    builtin_plugins: set[str],
    breaker_snapshot: JSONDict | None = None,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    plugin_name_value = p_data.get("plugin_name")
    if not isinstance(plugin_name_value, str) or not plugin_name_value:
        raise ValidationError("Plugin record missing plugin_name.")
    plugin_name = plugin_name_value
    state = p_data.get("state", PLUGIN_STATE_NOT_DETECTED) or PLUGIN_STATE_NOT_DETECTED
    compatibility_info = compatibility_from_record(p_data)
    breaker_info: JSONDict = {
        "state": CircuitBreakerState.CLOSED.value,
        "is_open": False,
        "failure_count": 0,
        "last_failure_at_ms": 0,
        "recovery_timeout_sec": None,
        "failure_window_sec": None,
        "failure_threshold": None,
    }
    routing_config = manager.dependencies.core.routing_config
    health_check_config = routing_config.health_checks if routing_config is not None else {}
    if isinstance(health_check_config, dict):
        if (config_value := health_check_config.get("RECOVERY_TIMEOUT_SEC")) is not None:
            breaker_info["recovery_timeout_sec"] = config_value
        if (config_value := health_check_config.get("FAILURE_WINDOW_SEC")) is not None:
            breaker_info["failure_window_sec"] = config_value
        if (config_value := health_check_config.get("FAILURE_THRESHOLD")) is not None:
            breaker_info["failure_threshold"] = config_value
    if breaker_snapshot:
        breaker_info.update(
            {
                snapshot_key: snapshot_value
                for snapshot_key, snapshot_value in breaker_snapshot.items()
                if snapshot_key in breaker_info
            },
        )
    breaker_state_value = breaker_info.get("state")
    breaker_state_text = (
        breaker_state_value.strip().lower() if isinstance(breaker_state_value, str) else ""
    )
    if breaker_state_text:
        breaker_info["state"] = breaker_state_text
        breaker_info["is_open"] = breaker_state_text == CircuitBreakerState.OPEN.value
    capability_keys = [
        "has_configuration",
        "supports_backend_installation",
        "supports_model_deletion",
        "supports_model_download",
        "supports_external_providers",
        "supports_gpu_binding",
        "local_resources",
        "local_models",
        "supports_cloning",
    ]
    capabilities: JSONDict = {
        key: coerce_bool_with_recovery(
            p_data,
            key,
            logger=logger,
            operation="plugins.state.hydration.coerce_plugin_bool",
            default=False,
        )
        for key in capability_keys
    }
    parsed_openai_caps = normalize_openai_capabilities(p_data.get("openai_capabilities"))
    capabilities["openai"] = parsed_openai_caps
    capabilities["external_provider_mode"] = (
        p_data.get("external_provider_mode") or ExternalProviderMode.NONE.value
    )
    user_enabled_once = coerce_bool_with_recovery(
        p_data,
        "user_enabled_once",
        logger=logger,
        operation="plugins.state.hydration.coerce_plugin_bool",
        default=False,
    )
    stats_entry = plugin_stats.get(plugin_name, {"model_count": 0, "provider_count": 0})
    stats_payload: JSONDict = {
        "model_count": coerce_non_negative_int_from_numberish(stats_entry.get("model_count", 0)),
        "provider_count": coerce_non_negative_int_from_numberish(
            stats_entry.get("provider_count", 0),
        ),
    }
    backend_variant_available_count = stats_entry.get("backend_variant_available_count")
    if backend_variant_available_count is not None:
        stats_payload["backend_variant_available_count"] = coerce_non_negative_int_from_numberish(
            backend_variant_available_count,
        )
    supports_backend_installation = bool(capabilities.get("supports_backend_installation"))
    if state == PLUGIN_STATE_NOT_DETECTED:
        installed = False
    elif not supports_backend_installation:
        installed = True
    else:
        installed = state != PLUGIN_STATE_BACKEND_NOT_INSTALLED
    technical_payload: JSONDict = {
        "max_concurrent_requests": p_data.get("max_concurrent_requests"),
        "file_path": p_data.get("file_path"),
        "file_hash": p_data.get("file_hash"),
        "first_seen_at_ms": p_data.get("first_seen_at_ms"),
        "last_seen_at_ms": p_data.get("last_seen_at_ms"),
    }
    if instance is not None:
        technical_payload["instance_loaded"] = True
    if status_payload is not None:
        technical_payload["status"] = status_payload
    display_name_value = p_data.get("name")
    if not isinstance(display_name_value, str) or not display_name_value.strip():
        raise ValidationError("Plugin record is missing required name field.")
    description_value = p_data.get("description_soaiplugin")
    if not isinstance(description_value, str):
        raise ValidationError("Plugin record is missing required description_soaiplugin field.")
    author_value = p_data.get("author_soaiplugin")
    if not isinstance(author_value, str):
        raise ValidationError("Plugin record is missing required author_soaiplugin field.")
    version_value = p_data.get("version_soaiplugin")
    if not isinstance(version_value, str) or not version_value.strip():
        raise ValidationError("Plugin record is missing required version_soaiplugin field.")
    license_soaiplugin_value = p_data.get("license_soaiplugin")
    if not isinstance(license_soaiplugin_value, str) or not license_soaiplugin_value.strip():
        raise ValidationError("Plugin record is missing required license_soaiplugin field.")
    url_value = p_data.get("website_soaiplugin")
    if not isinstance(url_value, str):
        raise ValidationError("Plugin record is missing required website_soaiplugin field.")
    core_compat_value = p_data.get("core_compat")
    if not isinstance(core_compat_value, str) or not core_compat_value.strip():
        raise ValidationError("Plugin record is missing required core_compat field.")
    dependencies = dependency_snapshot_from_record(p_data)
    return {
        "name": plugin_name,
        "display_name": display_name_value.strip(),
        "description_soaiplugin": description_value,
        "author_soaiplugin": author_value,
        "version_soaiplugin": version_value,
        "license_soaiplugin": license_soaiplugin_value.strip(),
        "website_soaiplugin": url_value,
        "website_backend": p_data.get("website_backend"),
        "license_managed_backend": p_data.get("license_managed_backend"),
        "model_repository": p_data.get("model_repository"),
        "model_types": as_json_list(_json_load_list(p_data.get("model_types"))),
        "external_provider_defaults": _json_load_dict(p_data.get("external_provider_defaults")),
        "core_compat": core_compat_value,
        "aliases": as_json_list(_json_load_list(p_data.get("aliases"))),
        "dependencies": {
            "plugins": as_json_list(list(dependencies.plugin_names)),
            "packages": as_json_list(list(dependencies.package_names)),
        },
        "modalities": as_json_list(_json_load_list(p_data.get("modalities"))),
        "state": state,
        "installed": installed,
        "is_builtin": plugin_name in builtin_plugins,
        "is_persistent": coerce_bool_with_recovery(
            p_data.get("persistent"),
            logger=logger,
            operation="plugins.state.hydration.coerce_plugin_bool",
            default=False,
        ),
        "is_enabled": (
            not compatibility_info.reason or compatibility_info.is_overridden or user_enabled_once
        )
        and state
        not in {
            ORCH_STATE_DISABLED,
            PLUGIN_STATE_INCOMPATIBLE,
        },
        "is_available": not compatibility_info.reason
        or compatibility_info.is_overridden
        or user_enabled_once,
        "permanently_disabled": bool(
            compatibility_info.reason and (not compatibility_info.can_override),
        ),
        "incompatibility": compatibility_to_payload(compatibility_info),
        "capabilities": capabilities,
        "stats": stats_payload,
        "technical": technical_payload,
        "circuit_breaker": breaker_info,
        "user_enabled_once": user_enabled_once,
    }
