"""SoAI - OpenAI images request validation [backend/features/api/routes/openai/images_request_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.image_model_validation import (
    is_gpt_image_model,
    validate_image_generation_model_fields,
)
from core.openai.request_fields import resolve_optional_model_name
from core.openai.request_options import extract_openai_bool_flag
from features.api.routes.openai.openai_default_model_resolution import (
    require_openai_default_model_id,
)
from features.api.runtime.openai_error_conversion import raise_openai_bad_request

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "preprocess_openai_image_generation_request_json",
    "validate_openai_images_request_fields",
)

_GPT_IMAGE_ONLY_FIELDS: tuple[str, ...] = (
    "background",
    "moderation",
    "output_compression",
    "output_format",
    "partial_images",
    "stream",
)


def validate_openai_images_request_fields(model: str, *, request_json: JSONDict) -> None:
    try:
        validate_image_generation_model_fields(
            model,
            has_response_format="response_format" in request_json,
            has_style="style" in request_json,
            has_background="background" in request_json,
            has_output_format="output_format" in request_json,
            has_output_compression="output_compression" in request_json,
        )
    except ValidationError as exception:
        raise_openai_bad_request(str(exception), cause=exception)


async def preprocess_openai_image_generation_request_json(
    api_context: ApiContext,
    request_json: JSONDict,
) -> None:
    explicit_model = resolve_optional_model_name(request_json)
    requested_quality = request_json.get("quality")
    requires_gpt_image = explicit_model is None and (
        any(key in request_json for key in _GPT_IMAGE_ONLY_FIELDS)
        or requested_quality in ("low", "medium", "high", "auto")
    )
    config_default_key = (
        "API.OPENAI.DEFAULT_IMAGE_MODEL_GPT"
        if requires_gpt_image
        else "API.OPENAI.DEFAULT_IMAGE_MODEL_DALLE"
    )
    model = await require_openai_default_model_id(
        api_context=api_context,
        explicit_model=explicit_model,
        required_openai_capability="images",
        trace_id=None,
        config_default_dotted_key=config_default_key,
        model_id_predicate=is_gpt_image_model if requires_gpt_image else None,
    )
    request_json["model"] = model
    request_json["_request_type"] = "image_generation"
    validate_openai_images_request_fields(model, request_json=request_json)
    if extract_openai_bool_flag(
        request_json,
        key="stream",
        default=False,
    ) and not is_gpt_image_model(model):
        raise_openai_bad_request("stream is only supported for GPT Image models.")
