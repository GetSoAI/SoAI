"""SoAI - Shared OpenAI image model and field validation [backend/core/openai/image_model_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = (
    "is_dalle_image_model",
    "is_gpt_image_model",
    "validate_image_background",
    "validate_image_count",
    "validate_image_edit_json_model",
    "validate_image_edit_quality",
    "validate_image_edit_response_format_model",
    "validate_image_generation_model_fields",
    "validate_image_input_fidelity",
    "validate_image_output_compression",
    "validate_image_output_format",
    "validate_image_partial_images",
    "validate_image_response_format",
)


def is_gpt_image_model(model: str) -> bool:
    return model.strip().lower().startswith("gpt-image-")


def is_dalle_image_model(model: str) -> bool:
    return model.strip().lower().startswith("dall-e-")


def validate_image_generation_model_fields(
    model: str,
    *,
    has_response_format: bool,
    has_style: bool,
    has_background: bool,
    has_output_format: bool,
    has_output_compression: bool,
) -> None:
    if is_gpt_image_model(model):
        if has_response_format:
            raise ValidationError("response_format is not supported for GPT Image models.")
        if has_style:
            raise ValidationError("style is not supported for GPT Image models.")
        return
    if is_dalle_image_model(model):
        if has_background:
            raise ValidationError("background is not supported for DALL·E models.")
        if has_output_format:
            raise ValidationError("output_format is not supported for DALL·E models.")
        if has_output_compression:
            raise ValidationError("output_compression is not supported for DALL·E models.")


def validate_image_edit_json_model(model: str) -> None:
    if is_dalle_image_model(model):
        raise ValidationError("JSON edits do not support DALL·E models.")


def validate_image_count(image_count: int | None) -> None:
    if image_count is not None and (image_count < 1 or image_count > 10):
        raise ValidationError("Field 'n' must be between 1 and 10.")


def validate_image_response_format(response_format: str | None) -> None:
    if response_format is not None and response_format not in ("url", "b64_json"):
        raise ValidationError("Field 'response_format' has an unsupported value.")


def validate_image_edit_response_format_model(model: str, response_format: str | None) -> None:
    if response_format is not None and not is_dalle_image_model(model):
        raise ValidationError("Field 'response_format' is only supported for DALL·E models.")


def validate_image_output_compression(output_compression: int | None) -> None:
    if output_compression is not None and (output_compression < 0 or output_compression > 100):
        raise ValidationError("Field 'output_compression' must be between 0 and 100.")


def validate_image_partial_images(partial_images: int | None) -> None:
    if partial_images is not None and (partial_images < 0 or partial_images > 3):
        raise ValidationError("Field 'partial_images' must be between 0 and 3.")


def validate_image_background(background: str | None) -> None:
    if background is not None and background not in ("transparent", "opaque", "auto"):
        raise ValidationError("Field 'background' has an unsupported value.")


def validate_image_output_format(output_format: str | None) -> None:
    if output_format is not None and output_format not in ("png", "jpeg", "webp"):
        raise ValidationError("Field 'output_format' has an unsupported value.")


def validate_image_input_fidelity(input_fidelity: str | None) -> None:
    if input_fidelity is not None and input_fidelity not in ("high", "low"):
        raise ValidationError("Field 'input_fidelity' has an unsupported value.")


def validate_image_edit_quality(quality: str | None) -> None:
    if quality is not None and quality not in ("standard", "low", "medium", "high", "auto"):
        raise ValidationError("Field 'quality' has an unsupported value.")
