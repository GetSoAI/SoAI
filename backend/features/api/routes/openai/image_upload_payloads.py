"""SoAI - OpenAI image upload payload construction [backend/features/api/routes/openai/image_upload_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.image_model_validation import (
    is_gpt_image_model,
    validate_image_background,
    validate_image_count,
    validate_image_edit_quality,
    validate_image_edit_response_format_model,
    validate_image_input_fidelity,
    validate_image_output_compression,
    validate_image_output_format,
    validate_image_partial_images,
    validate_image_response_format,
)
from features.api.routes.multipart_field_values import (
    field_optional_bool,
    field_optional_int,
    field_optional_str,
    field_required_str,
)
from features.api.routes.openai.image_upload_staged_validation import (
    validate_staged_image_parts,
)
from features.api.routes.openai.openai_default_model_resolution import (
    require_openai_default_model_id,
)
from features.api.routes.openai.streaming_upload_error_handling import (
    extract_optional_single_file,
    extract_single_file,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingMultipartResult,
    )
    from features.api.runtime.context import ApiContext

__all__ = (
    "build_openai_image_edit_upload_payloads",
    "build_openai_image_variation_upload_payloads",
)

_GPT_IMAGE_EDIT_ONLY_FIELDS: tuple[str, ...] = (
    "background",
    "input_fidelity",
    "output_compression",
    "output_format",
    "partial_images",
    "stream",
)


async def build_openai_image_variation_upload_payloads(
    *,
    api_context: ApiContext,
    parsed: StreamingMultipartResult,
    max_upload_bytes: int,
) -> tuple[JSONDict, JSONDict]:
    model = await require_openai_default_model_id(
        api_context=api_context,
        explicit_model=field_optional_str(parsed.fields, "model"),
        required_openai_capability="image_variations",
        trace_id=None,
        config_default_dotted_key="API.OPENAI.DEFAULT_IMAGE_MODEL_DALLE",
    )
    image_count = field_optional_int(parsed.fields, "n")
    validate_image_count(image_count)
    size = field_optional_str(parsed.fields, "size")
    user = field_optional_str(parsed.fields, "user")
    response_format = field_optional_str(parsed.fields, "response_format")
    validate_image_response_format(response_format)
    image_part = extract_single_file(parsed.files, "image")
    validate_staged_image_parts(parts=[image_part], max_upload_bytes=max_upload_bytes)
    request_json: JSONDict = {"model": model}
    if response_format is not None:
        request_json["response_format"] = response_format
    command_fields: JSONDict = {
        "image_temp_path": image_part.temp_path,
        "original_filename": image_part.original_filename,
        "required_capabilities": ("image_variations",),
        "required_modalities": ("vision",),
        "model": model,
    }
    _add_optional_image_command_fields(
        command_fields,
        image_count=image_count,
        size=size,
        response_format=response_format,
        user=user,
    )
    return command_fields, request_json


async def build_openai_image_edit_upload_payloads(
    *,
    api_context: ApiContext,
    parsed: StreamingMultipartResult,
    max_upload_bytes: int,
) -> tuple[JSONDict, JSONDict]:
    prompt = field_required_str(parsed.fields, "prompt")
    explicit_model = field_optional_str(parsed.fields, "model")
    requested_quality = field_optional_str(parsed.fields, "quality")
    image_file_count = sum(
        1 for part in parsed.files if part.field_name in ("image", "image[]") and part.temp_path
    )
    requires_gpt_image = explicit_model is None and (
        any(field in parsed.fields for field in _GPT_IMAGE_EDIT_ONLY_FIELDS)
        or requested_quality in ("low", "medium", "high", "auto")
        or image_file_count > 1
    )
    model = await require_openai_default_model_id(
        api_context=api_context,
        explicit_model=explicit_model,
        required_openai_capability="image_edits",
        trace_id=None,
        config_default_dotted_key="API.OPENAI.DEFAULT_IMAGE_MODEL_GPT",
        model_id_predicate=is_gpt_image_model if requires_gpt_image else None,
    )
    command_fields = _build_image_edit_command_fields(
        parsed=parsed,
        model=model,
        prompt=prompt,
        max_upload_bytes=max_upload_bytes,
    )
    return command_fields, {"prompt": prompt, "model": model}


def _build_image_edit_command_fields(
    *,
    parsed: StreamingMultipartResult,
    model: str,
    prompt: str,
    max_upload_bytes: int,
) -> JSONDict:
    image_count = field_optional_int(parsed.fields, "n")
    validate_image_count(image_count)
    response_format = field_optional_str(parsed.fields, "response_format")
    validate_image_response_format(response_format)
    validate_image_edit_response_format_model(model, response_format)
    output_format = field_optional_str(parsed.fields, "output_format")
    validate_image_output_format(output_format)
    output_compression = field_optional_int(parsed.fields, "output_compression")
    validate_image_output_compression(output_compression)
    input_fidelity = field_optional_str(parsed.fields, "input_fidelity")
    validate_image_input_fidelity(input_fidelity)
    partial_images = field_optional_int(parsed.fields, "partial_images")
    validate_image_partial_images(partial_images)
    background = field_optional_str(parsed.fields, "background")
    validate_image_background(background)
    quality = field_optional_str(parsed.fields, "quality")
    validate_image_edit_quality(quality)
    image_parts = [
        part for part in parsed.files if part.field_name in ("image", "image[]") and part.temp_path
    ]
    if not image_parts:
        raise ValidationError("Missing required file field 'image'.")
    if len(image_parts) > 16:
        raise ValidationError("Field 'image' supports up to 16 files.")
    mask_part = extract_optional_single_file(parsed.files, "mask")
    validate_staged_image_parts(parts=image_parts, max_upload_bytes=max_upload_bytes)
    if mask_part is not None:
        validate_staged_image_parts(parts=[mask_part], max_upload_bytes=max_upload_bytes)
    command_fields: JSONDict = {
        "image_temp_paths": tuple(part.temp_path for part in image_parts),
        "original_filenames": tuple(part.original_filename for part in image_parts),
        "required_capabilities": ("image_edits",),
        "required_modalities": ("vision",),
        "prompt": prompt,
        "model": model,
    }
    if mask_part is not None:
        command_fields["mask_temp_path"] = mask_part.temp_path
    _add_optional_image_command_fields(
        command_fields,
        image_count=image_count,
        size=field_optional_str(parsed.fields, "size"),
        user=field_optional_str(parsed.fields, "user"),
        background=background,
        response_format=response_format,
        output_format=output_format,
        output_compression=output_compression,
        input_fidelity=input_fidelity,
        stream=field_optional_bool(parsed.fields, "stream"),
        partial_images=partial_images,
        quality=quality,
    )
    return command_fields


def _add_optional_image_command_fields(command_fields: JSONDict, **values: JSONValue) -> None:
    for key, value in values.items():
        if value is not None:
            command_fields[key] = value
