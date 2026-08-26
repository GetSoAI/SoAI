"""SoAI - Plugin catalog routes [backend/features/api/routes/plugins/plugin_catalog_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Query, Request, status
from starlette.responses import JSONResponse, Response

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.manual_install_paths import build_manual_install_path_payload
from core.models.remote_model_search_error import RemoteModelSearchError
from core.plugins.errors import PluginIncompatibleError
from core.runtime.network_policy import OfflineModeError
from core.state.access import AccessAction
from core.types.json import JSONDict
from core.types.json_value import filter_json_mapping_strict
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    get_openai_capability_taxonomy,
    resolve_api_context,
)
from features.api.runtime.errors import (
    raise_bad_gateway,
    raise_not_found,
    raise_offline_mode,
    raise_server_error,
    raise_unauthorized,
)
from features.api.runtime.plugin_compatibility import handle_plugin_incompatible_error
from features.api.schemas.models import ModelVariant, RemoteModelSearchResult

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.plugin_catalog_routes"
OPERATION_API_PLUGIN_GET_MODEL_VARIANTS_FOR_PLUGIN = "api_plugin.get_model_variants_for_plugin"
OPERATION_API_PLUGIN_SEARCH_REMOTE_MODELS_FOR_PLUGIN = "api_plugin.search_remote_models_for_plugin"


def _redact_plugin_technical_fields(
    plugins: list[JSONDict],
) -> list[JSONDict]:
    redacted: list[JSONDict] = []
    for plugin_entry in plugins:
        payload = dict(plugin_entry)
        technical = payload.get("technical")
        if isinstance(technical, dict):
            technical_payload = dict(technical)
            technical_payload.pop("file_path", None)
            technical_payload.pop("file_hash", None)
            payload["technical"] = technical_payload
        redacted.append(payload)
    return redacted


async def get_plugin_list_snapshot(api_context: ApiContext) -> list[JSONDict]:
    plugins = await api_context.dependencies.plugin_manager.list_plugins()
    return _redact_plugin_technical_fields(plugins)


def register_routes(routers: ApiRouters) -> None:
    plugin_read_deps = require_action_dependencies(AccessAction.PLUGIN_READ)
    plugin_admin_deps = require_action_dependencies(AccessAction.PLUGIN_ADMIN)

    @routers.plugins.get("", dependencies=plugin_read_deps)
    async def get_plugin_list(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        snapshot = await get_plugin_list_snapshot(api_context)
        return JSONResponse(content=snapshot)

    @routers.plugins.get("/capabilities-manifest", dependencies=plugin_read_deps)
    async def get_plugin_capabilities_manifest() -> Response:
        manifest = get_openai_capability_taxonomy()
        return JSONResponse(content=manifest)

    @routers.plugins.get("/manual-install", dependencies=plugin_admin_deps)
    async def get_plugin_manual_install_path(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        payload = build_manual_install_path_payload(
            config=api_context.dependencies.config,
            files=api_context.dependencies.files,
            resource_type="plugins",
            config_key="PLUGINS.PATHS.PLUGINS",
        )
        payload_json = filter_json_mapping_strict(
            payload,
            error_message="Plugin manual install payload must be JSON-compatible.",
        )
        return JSONResponse(content=payload_json)

    @routers.plugins.get(
        "/{plugin_name}/models/{model_id:path}/variants",
        response_model=list[ModelVariant],
        dependencies=plugin_read_deps,
    )
    async def get_model_variants_for_plugin(
        request: Request,
        plugin_name: str,
        model_id: str,
        include_speed_tests: bool = Query(False),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> list[ModelVariant]:
        try:
            raw_variants = await api_context.dependencies.plugin_manager.describe_model_variants(
                plugin_name,
                model_id,
                include_speed_tests=include_speed_tests,
            )
            return [ModelVariant.model_validate(entry) for entry in raw_variants]
        except PluginIncompatibleError as exception:
            handle_plugin_incompatible_error(request, exception)
        except (ValidationError, ValueError) as exception:
            raise_not_found(request, str(exception))
        except OfflineModeError as exception:
            raise_offline_mode(request, str(exception))
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Error getting variants",
                operation=OPERATION_API_PLUGIN_GET_MODEL_VARIANTS_FOR_PLUGIN,
                details={"plugin": plugin_name, "model_id": model_id},
            )
        raise_server_error(
            request,
            "The plugin failed to process the variant discovery request.",
            error_type="plugin_error",
        )

    @routers.plugins.get(
        "/{plugin_name}/model-search",
        response_model=list[RemoteModelSearchResult],
        dependencies=plugin_read_deps,
    )
    async def search_remote_models_for_plugin(
        request: Request,
        plugin_name: str,
        query: str = Query(..., min_length=2, max_length=80, alias="q"),
        limit: int = Query(10, ge=1, le=1000),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> list[RemoteModelSearchResult]:
        try:
            raw_results = await api_context.dependencies.plugin_manager.search_remote_models(
                plugin_name,
                query,
                limit=limit,
            )
            return [RemoteModelSearchResult.model_validate(entry) for entry in raw_results]
        except (ValidationError, ValueError) as exception:
            raise_not_found(request, str(exception))
        except RemoteModelSearchError as exception:
            status_code = (
                status.HTTP_401_UNAUTHORIZED
                if exception.status_code in (401, 403)
                else status.HTTP_502_BAD_GATEWAY
            )
            if status_code == status.HTTP_401_UNAUTHORIZED:
                raise_unauthorized(request, str(exception), error_type="remote_search_error")
            raise_bad_gateway(request, str(exception), error_type="remote_search_error")
        except OfflineModeError as exception:
            raise_offline_mode(request, str(exception))
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Remote model search failed",
                operation=OPERATION_API_PLUGIN_SEARCH_REMOTE_MODELS_FOR_PLUGIN,
                details={"plugin": plugin_name},
            )
            raise_server_error(
                request,
                "The plugin failed to process the search request.",
                error_type="plugin_error",
            )
