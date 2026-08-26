"""SoAI - REST API endpoints for managing YAML configurations [backend/features/api/routes/configs/configs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING

from fastapi import Depends, Request, status
from fastapi.responses import JSONResponse
from ruamel.yaml.comments import CommentedMap
from starlette.responses import Response

from core.config.merge import deep_merge_config, expand_dot_notation
from core.config.protocols import ConfigManagerProtocol
from core.config.redacted_patch_values import remove_redacted_sensitive_patch_values
from core.config.value_validation import is_config_dict
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConfigurationError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.plugins.errors import PluginCapabilityError
from core.security.response_redaction import (
    REDACTED_PLACEHOLDER,
    redact_response_payload,
)
from core.serialization.json import normalize_for_json
from core.state.access import AccessAction
from core.types.json import is_json_value
from features.api.routes.configs.gpu_binding_validation import validate_gpu_binding_patch
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    get_request_trace_id,
    resolve_api_context,
)
from features.api.runtime.errors import (
    raise_action_not_supported,
    raise_invalid_request,
    raise_not_found,
    raise_server_error,
)
from features.api.runtime.metadata_values import is_sensitive_key
from features.api.schemas.configs import ConfigPatch

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.configs"
OPERATION_API_CONFIGS_GET = "api_configs.get"
OPERATION_API_CONFIGS_PATCH = "api_configs.patch"


def _ensure_plain_config_mapping(
    request: Request,
    config_name: str,
    payload: JSONValue,
) -> JSONDict:
    if not isinstance(payload, Mapping):
        raise_server_error(
            request,
            f"Failed to serialize configuration '{config_name}'.",
        )
    normalized: JSONDict = {}
    for key, value in payload.items():
        if not is_json_value(value):
            raise_server_error(
                request,
                f"Configuration '{config_name}' contains non-JSON value for key '{key}'.",
            )
        normalized[key] = value
    return normalized


def _clear_api_rate_limit_path_overrides_for_merge(
    current_config: CommentedMap,
    expanded_changes: JSONDict,
) -> None:
    api_patch = expanded_changes.get("API")
    openai_api_patch = api_patch.get("OPENAI") if isinstance(api_patch, Mapping) else None
    if not isinstance(openai_api_patch, Mapping):
        return
    rate_limiting_patch = openai_api_patch.get("RATE_LIMITING")
    if not isinstance(rate_limiting_patch, Mapping):
        return
    existing_api = current_config.get("API")
    existing_openai_api = existing_api.get("OPENAI") if isinstance(existing_api, Mapping) else None
    if not isinstance(existing_openai_api, MutableMapping):
        return
    existing_rate_limiting = existing_openai_api.get("RATE_LIMITING")
    if not isinstance(existing_rate_limiting, MutableMapping):
        return
    routers_patch = rate_limiting_patch.get("ROUTERS")
    if not isinstance(routers_patch, Mapping):
        return
    if not routers_patch:
        existing_rate_limiting["ROUTERS"] = {}
        return
    existing_routers = existing_rate_limiting.get("ROUTERS")
    if not isinstance(existing_routers, MutableMapping):
        return
    for router_name, router_patch in routers_patch.items():
        if not isinstance(router_name, str):
            continue
        if not isinstance(router_patch, Mapping):
            continue
        if "PATHS" not in router_patch:
            continue
        existing_router = existing_routers.get(router_name)
        if not isinstance(existing_router, MutableMapping):
            continue
        existing_router["PATHS"] = {}


def register_routes(routers: ApiRouters) -> None:
    @routers.configs.get(
        "/",
        include_in_schema=False,
        dependencies=require_action_dependencies(AccessAction.CONFIG_PATCH),
    )
    @routers.configs.get("", dependencies=require_action_dependencies(AccessAction.CONFIG_PATCH))
    async def list_all_configs(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        config_manager = api_context.dependencies.config_manager
        configs = await config_manager.list_manageable_configs()
        return JSONResponse(content=configs)

    async def _require_manageable_config(
        request: Request,
        config_manager: ConfigManagerProtocol,
        config_name: str,
    ) -> None:
        if config_name not in await config_manager.list_manageable_configs():
            raise_not_found(
                request,
                f"Configuration '{config_name}' not found or is not manageable.",
            )

    @routers.configs.get(
        "/{config_name}",
        dependencies=require_action_dependencies(AccessAction.CONFIG_PATCH),
    )
    async def get_specific_config(
        request: Request,
        config_name: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        config_manager = api_context.dependencies.config_manager
        await _require_manageable_config(request, config_manager, config_name)
        try:
            config_data = await config_manager.load_config(config_name, force_reload=True)
            payload = normalize_for_json(config_data) if config_data is not None else None
            if not isinstance(payload, dict) or not payload:
                raise_not_found(
                    request,
                    f"Configuration file for '{config_name}' does not exist or is empty.",
                )
            normalized = _ensure_plain_config_mapping(request, config_name, payload)
            redacted = redact_response_payload(normalized, preserve_empty_sensitive_strings=True)
            return JSONResponse(content=redacted)
        except RECOVERABLE_EXCEPTIONS as exception:
            trace_id = get_request_trace_id(request)
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message=f"Unexpected error loading config '{config_name}'.",
                trace_id=trace_id,
                operation=OPERATION_API_CONFIGS_GET,
                details={"config_name": config_name},
            )
            raise_server_error(request, f"Failed to load configuration '{config_name}'.")

    @routers.configs.patch(
        "/{config_name}",
        dependencies=require_action_dependencies(AccessAction.CONFIG_PATCH),
    )
    async def patch_specific_config(
        request: Request,
        config_name: str,
        payload: ConfigPatch,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        config_manager = api_context.dependencies.config_manager
        plugin_manager_instance = api_context.dependencies.plugin_manager
        await _require_manageable_config(request, config_manager, config_name)
        if config_name != "core":
            try:
                await plugin_manager_instance.ensure_plugin_capability(
                    config_name,
                    "SUPPORTS_CONFIGURATION",
                    "Managed Configuration",
                )
            except PluginCapabilityError as exception:
                raise_action_not_supported(request, str(exception))

        def _redact(value: JSONValue) -> JSONValue:
            if isinstance(value, dict):
                redacted: JSONDict = {}
                for config_key, config_value in value.items():
                    if isinstance(config_key, str) and is_sensitive_key(config_key):
                        redacted[config_key] = "***"
                    else:
                        redacted[config_key] = _redact(config_value)
                return redacted
            if isinstance(value, list):
                return [_redact(item) for item in value]
            return value

        log_audit_event(request, "PATCH_CONFIG", config_name, {"changes": _redact(payload.changes)})
        try:
            expanded_changes = remove_redacted_sensitive_patch_values(
                expand_dot_notation(payload.changes),
                placeholder=REDACTED_PLACEHOLDER,
            )
            current_config_data = await config_manager.load_config(config_name, force_reload=True)
            if current_config_data is None:
                current_plain_config: JSONDict = {}
            else:
                if not is_config_dict(current_config_data):
                    raise_server_error(
                        request,
                        f"Configuration '{config_name}' is not a mapping.",
                    )
                current_plain_config = _ensure_plain_config_mapping(
                    request,
                    config_name,
                    normalize_for_json(current_config_data),
                )
            await validate_gpu_binding_patch(
                request,
                config_name,
                expanded_changes,
                current_plain_config,
                api_context,
            )

            def updater(current_config: CommentedMap) -> CommentedMap:
                _clear_api_rate_limit_path_overrides_for_merge(current_config, expanded_changes)
                if not is_config_dict(current_config):
                    raise ValidationError("Current configuration is not config-compatible.")
                merged_config = deep_merge_config(
                    current_config,
                    expanded_changes,
                    expand_dots=False,
                )
                if isinstance(merged_config, CommentedMap):
                    return merged_config
                commented_config = CommentedMap(merged_config)
                return commented_config

            await config_manager.update_config_transactionally(
                config_name,
                source="api:config_patch",
                updater=updater,
                changed_keys=None,
            )
            if config_name != "core":
                await plugin_manager_instance.refresh_plugin_runtime_configuration(
                    config_name,
                    auto_load=False,
                )
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "success": True,
                    "message": "Configuration saved; applying updates.",
                },
            )
        except (ConfigurationError, ValidationError, ValueError, TypeError) as exception:
            raise_invalid_request(
                request,
                f"Failed to save configuration '{config_name}': {exception}",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            trace_id = get_request_trace_id(request)
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message=f"Unexpected error saving config '{config_name}'.",
                trace_id=trace_id,
                operation=OPERATION_API_CONFIGS_PATCH,
                details={"config_name": config_name},
            )
            raise_server_error(request, f"Failed to save configuration '{config_name}'.")
