"""SoAI - OpenAI Responses strict passthrough endpoint wiring [backend/features/api/routes/openai/responses/responses_endpoint_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from starlette.responses import Response

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from features.api.openai.request_payloads import parse_json_object_body
from features.api.routes.openai.responses.background_start import (
    start_background_response_request,
)
from features.api.routes.openai.responses.compaction_expansion import (
    expand_responses_compaction_items,
)
from features.api.routes.openai.responses.create_request_validation import (
    infer_required_capabilities,
    infer_required_modalities,
    validate_responses_create_payload_or_response,
)
from features.api.routes.openai.responses.effective_input_state import (
    store_effective_input_items,
)
from features.api.routes.openai.responses.input_tokens_items import (
    build_effective_input_items_from_payload,
)
from features.api.routes.openai.responses.model_resolution import (
    resolve_responses_model_id_from_payload,
)
from features.api.routes.openai.responses.passthrough_non_streaming import (
    wait_for_non_streaming_responses_result,
)
from features.api.routes.openai.responses.passthrough_task_setup import (
    ResponsesTaskSetupResult,
    setup_responses_inference_task,
)
from features.api.routes.openai.responses.payload_parsing import (
    parse_optional_responses_input_value_or_response,
)
from features.api.routes.openai.responses.streaming_generator.response_builder import (
    create_passthrough_responses_streaming_response,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.openai_request_validation import (
    build_openai_invalid_request_response,
)
from features.api.runtime.responses import (
    apply_operation_id_header,
    apply_task_id_header,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "handle_responses",
    "register_routes",
)

LOGGER_NAME = "SoAI.features.api.responses_endpoint_routes"
OPERATION_RESPONSES_EXPAND_COMPACTION = "features.api.responses_endpoint_routes.expand_compaction"


async def handle_responses(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    context = request.state.context
    logger = get_logger(LOGGER_NAME)
    parsed = await parse_json_object_body(request, trace_id=context.trace_id)
    if isinstance(parsed, Response):
        return parsed
    payload_json: dict[str, JSONValue] = parsed
    input_value = parse_optional_responses_input_value_or_response(
        payload_json,
        trace_id=context.trace_id,
    )
    if isinstance(input_value, Response):
        return input_value
    if input_value is not None:
        try:
            payload_json["input"] = expand_responses_compaction_items(
                database_openai_responses=api_context.dependencies.database_openai_responses,
                input_value=input_value,
            )
        except ValidationError as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed expanding compaction items.",
                trace_id=context.trace_id,
                operation=OPERATION_RESPONSES_EXPAND_COMPACTION,
                level="debug",
            )
            return build_openai_invalid_request_response(
                message="Invalid compaction item.",
                param="input",
                trace_id=context.trace_id,
            )
    validated_payload = validate_responses_create_payload_or_response(
        payload_json,
        trace_id=context.trace_id,
    )
    if isinstance(validated_payload, Response):
        return validated_payload
    payload_json = validated_payload
    model = await resolve_responses_model_id_from_payload(
        api_context=api_context,
        trace_id=context.trace_id,
        payload_json=payload_json,
    )
    payload_json["model"] = model
    inferred_capabilities = infer_required_capabilities(payload_json)
    required_capabilities = tuple(dict.fromkeys(("responses", *inferred_capabilities)))
    required_modalities = infer_required_modalities(payload_json)
    api_context.dependencies.metrics_manager.increment_counter(
        "api",
        "openai",
        "requests_total_responses",
    )
    stream = payload_json.get("stream") is True
    background = payload_json.get("background") is True
    effective_input_items = await build_effective_input_items_from_payload(
        api_context,
        request,
        payload_json=payload_json,
    )
    if isinstance(effective_input_items, Response):
        return effective_input_items
    store_effective_input_items(request, effective_input_items)
    payload_json["input"] = list(effective_input_items)
    task_request_json: JSONDict = dict(payload_json)
    task_request_json.pop("background", None)
    task_setup = await setup_responses_inference_task(
        request=request,
        api_context=api_context,
        request_json=task_request_json,
        required_capabilities=required_capabilities,
        required_modalities=required_modalities,
        event_type_label="responses",
    )
    if not isinstance(task_setup, ResponsesTaskSetupResult):
        return task_setup
    if background:
        return await start_background_response_request(
            request=request,
            api_context=api_context,
            task_setup=task_setup,
            model=model,
            effective_input_items=effective_input_items,
            stream_enabled=stream,
        )
    if stream:
        return create_passthrough_responses_streaming_response(
            request=request,
            api_context=api_context,
            task_setup=task_setup,
            request_json=payload_json,
        )
    result = await wait_for_non_streaming_responses_result(
        request=request,
        api_context=api_context,
        task_setup=task_setup,
        request_json=payload_json,
    )
    response = result
    response.headers.update(result.headers)
    apply_task_id_header(
        response,
        result.headers.get("X-SoAI-Task-Id") or task_setup.task.task_id,
    )
    apply_operation_id_header(
        response,
        result.headers.get("X-SoAI-Operation-Id") or context.trace_id,
    )
    return response


def register_routes(routers: ApiRouters) -> None:
    routers.openai_public.post(
        "/responses",
        tags=["OpenAI Responses"],
        dependencies=[openai_api_dependency()],
    )(handle_responses)
