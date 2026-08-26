"""SoAI - OpenAI model and metadata endpoints [backend/features/api/routes/openai/openai_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.openai.model_capability_catalog import (
    build_model_capability_catalog_entry,
    build_model_capability_catalog_response,
)
from core.openai.models_payloads import (
    project_openai_model_list_response,
    project_openai_model_object,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, get_request_trace_id, resolve_api_context
from features.api.runtime.errors import raise_forbidden, raise_not_found, raise_server_error

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.openai_models"
OPERATION_LIST_MODELS_OPENAI = "features.api.routes.openai.openai_models.list_models_openai"
OPERATION_GET_MODEL_DETAILS_OPENAI = (
    "features.api.routes.openai.openai_models.get_model_details_openai"
)


def register_routes(routers: ApiRouters) -> None:
    @routers.openai_public.get(
        "/models",
        tags=["OpenAI Model Management"],
        dependencies=[openai_api_dependency()],
    )
    async def list_models_openai(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        metrics_manager = api_context.dependencies.metrics_manager
        metrics_manager.increment_counter("api", "openai", "list_models_requests")
        try:
            model_information_service = api_context.dependencies.model_information_service
            raw = await model_information_service.model_get_openai_formatted_list()
        except ValidationError as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="OpenAI model list build failed due to invalid server state.",
                trace_id=get_request_trace_id(request),
                operation=OPERATION_LIST_MODELS_OPENAI,
                level="error",
            )
            raise_server_error(
                request,
                "Failed to build model list.",
                error_type="invalid_request_error",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Failed to build OpenAI model list.",
                trace_id=get_request_trace_id(request),
                operation=OPERATION_LIST_MODELS_OPENAI,
                level="error",
            )
            raise_server_error(
                request,
                "Failed to build model list.",
                error_type="invalid_request_error",
            )
        try:
            catalog = build_model_capability_catalog_response(raw)
            return JSONResponse(content=project_openai_model_list_response(catalog))
        except ValidationError as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="OpenAI model list payload is invalid.",
                trace_id=get_request_trace_id(request),
                operation=OPERATION_LIST_MODELS_OPENAI,
                level="error",
            )
            raise_server_error(
                request,
                "Failed to build model list.",
                error_type="invalid_request_error",
            )

    @routers.openai_public.get(
        "/models/{model:path}",
        tags=["OpenAI Model Management"],
        dependencies=[openai_api_dependency()],
    )
    async def get_model_details_openai(
        request: Request,
        model: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        metrics_manager = api_context.dependencies.metrics_manager
        metrics_manager.increment_counter("api", "openai", "get_model_details_requests")
        try:
            model_details = (
                await api_context.dependencies.model_information_service.model_get_openai_formatted(
                    model,
                    api_context.dependencies.model_resolution_service.model_resolve_to_universal_id,
                )
            )
        except ValidationError as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="OpenAI model details build failed due to invalid server state.",
                trace_id=get_request_trace_id(request),
                operation=OPERATION_GET_MODEL_DETAILS_OPENAI,
                level="error",
            )
            raise_server_error(
                request,
                "Failed to fetch model details.",
                error_type="invalid_request_error",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Failed to build OpenAI model details.",
                trace_id=get_request_trace_id(request),
                operation=OPERATION_GET_MODEL_DETAILS_OPENAI,
                level="error",
            )
            raise_server_error(
                request,
                "Failed to fetch model details.",
                error_type="invalid_request_error",
            )
        if not model_details:
            raise_not_found(
                request,
                f"The model '{model}' does not exist.",
                error_type="model_not_found",
            )
        try:
            return JSONResponse(
                content=project_openai_model_object(
                    build_model_capability_catalog_entry(
                        model_details,
                        context="OpenAI model capability catalog details",
                    ),
                    context="OpenAI model details payload",
                ),
            )
        except ValidationError as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="OpenAI model details payload is invalid.",
                trace_id=get_request_trace_id(request),
                operation=OPERATION_GET_MODEL_DETAILS_OPENAI,
                level="error",
            )
            raise_server_error(
                request,
                "Failed to fetch model details.",
                error_type="invalid_request_error",
            )

    @routers.openai_public.delete(
        "/models/{model:path}",
        tags=["OpenAI Model Management"],
        dependencies=[openai_api_dependency()],
    )
    async def delete_model_openai(
        request: Request,
        model: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        metrics_manager = api_context.dependencies.metrics_manager
        metrics_manager.increment_counter("api", "openai", "delete_model_requests")
        try:
            model_details = (
                await api_context.dependencies.model_information_service.model_get_openai_formatted(
                    model,
                    api_context.dependencies.model_resolution_service.model_resolve_to_universal_id,
                )
            )
        except ValidationError as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="OpenAI model delete preflight failed due to invalid server state.",
                trace_id=get_request_trace_id(request),
                operation=OPERATION_GET_MODEL_DETAILS_OPENAI,
                level="error",
            )
            raise_server_error(
                request,
                "Failed to fetch model details.",
                error_type="invalid_request_error",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Failed to build OpenAI model details for delete.",
                trace_id=get_request_trace_id(request),
                operation=OPERATION_GET_MODEL_DETAILS_OPENAI,
                level="error",
            )
            raise_server_error(
                request,
                "Failed to fetch model details.",
                error_type="invalid_request_error",
            )
        if not model_details:
            raise_not_found(
                request,
                f"The model '{model}' does not exist.",
                error_type="model_not_found",
            )
        raise_forbidden(
            request,
            "Model deletion is not supported by this SoAI installation.",
            error_type="permission_denied",
        )
