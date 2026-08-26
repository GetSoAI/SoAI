"""SoAI - OpenAI message content validation helpers [backend/core/openai/message_content_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("validate_message_content_json",)


def validate_message_content_json(
    content_value: JSONValue,
    *,
    param_prefix: str = "content",
) -> str | list[JSONDict]:
    if isinstance(content_value, str):
        return content_value
    if isinstance(content_value, list):
        if not content_value:
            raise ValidationError(
                "Message content array cannot be empty.",
                details={"param": param_prefix},
            )
        validated_parts: list[JSONDict] = []
        for index, part in enumerate(content_value):
            if not isinstance(part, dict):
                raise ValidationError(
                    f"Content part at index {index} must be a dict.",
                    details={"param": f"{param_prefix}[{index}]"},
                )
            part_type_value = part.get("type")
            if not isinstance(part_type_value, str) or not part_type_value.strip():
                raise ValidationError(
                    f"Content part at index {index} has invalid type '{part_type_value}'.",
                    details={"param": f"{param_prefix}[{index}].type"},
                )
            part_type = part_type_value.strip()
            if part_type not in ("text", "refusal", "image_url", "input_audio", "file"):
                raise ValidationError(
                    f"Content part at index {index} has invalid type '{part_type}'.",
                    details={"param": f"{param_prefix}[{index}].type"},
                )
            if part_type == "text":
                text_value = part.get("text")
                if not isinstance(text_value, str):
                    raise ValidationError(
                        f"Text content part at index {index} missing required 'text' field.",
                        details={"param": f"{param_prefix}[{index}].text"},
                    )
                if not text_value.strip():
                    raise ValidationError(
                        f"Text content part at index {index} has empty 'text'.",
                        details={"param": f"{param_prefix}[{index}].text"},
                    )
            if part_type == "refusal":
                refusal_value = part.get("refusal")
                if not isinstance(refusal_value, str):
                    raise ValidationError(
                        f"Refusal content part at index {index} missing required 'refusal' field.",
                        details={"param": f"{param_prefix}[{index}].refusal"},
                    )
                if not refusal_value.strip():
                    raise ValidationError(
                        f"Refusal content part at index {index} has empty 'refusal'.",
                        details={"param": f"{param_prefix}[{index}].refusal"},
                    )
            if part_type == "image_url":
                image_url_obj = part.get("image_url")
                if not isinstance(image_url_obj, dict):
                    raise ValidationError(
                        f"Image URL content part at index {index} missing 'image_url' object.",
                        details={"param": f"{param_prefix}[{index}].image_url"},
                    )
                url = image_url_obj.get("url")
                if not isinstance(url, str):
                    raise ValidationError(
                        f"Image URL content part at index {index} missing 'image_url.url' string field.",
                        details={"param": f"{param_prefix}[{index}].image_url.url"},
                    )
                if not url.strip():
                    raise ValidationError(
                        f"Image URL content part at index {index} has empty 'image_url.url'.",
                        details={"param": f"{param_prefix}[{index}].image_url.url"},
                    )
            if part_type == "input_audio":
                input_audio_obj = part.get("input_audio")
                if not isinstance(input_audio_obj, dict):
                    raise ValidationError(
                        f"Audio content part at index {index} missing 'input_audio' object.",
                        details={"param": f"{param_prefix}[{index}].input_audio"},
                    )
                data_value = input_audio_obj.get("data")
                if not isinstance(data_value, str):
                    raise ValidationError(
                        f"Audio content part at index {index} missing 'input_audio.data' string field.",
                        details={"param": f"{param_prefix}[{index}].input_audio.data"},
                    )
                if not data_value.strip():
                    raise ValidationError(
                        f"Audio content part at index {index} has empty 'input_audio.data'.",
                        details={"param": f"{param_prefix}[{index}].input_audio.data"},
                    )
                format_value = input_audio_obj.get("format")
                if format_value is not None and format_value not in ("wav", "mp3"):
                    raise ValidationError(
                        f"Audio content part at index {index} has invalid 'input_audio.format' value '{format_value}'.",
                        details={"param": f"{param_prefix}[{index}].input_audio.format"},
                    )
            if part_type == "file":
                file_obj = part.get("file")
                if not isinstance(file_obj, dict):
                    raise ValidationError(
                        f"File content part at index {index} missing 'file' object.",
                        details={"param": f"{param_prefix}[{index}].file"},
                    )
                filename_value = file_obj.get("filename")
                file_data_value = file_obj.get("file_data")
                file_id_value = file_obj.get("file_id")
                if filename_value is not None and not isinstance(filename_value, str):
                    raise ValidationError(
                        f"File content part at index {index} has invalid 'file.filename' value.",
                        details={"param": f"{param_prefix}[{index}].file.filename"},
                    )
                if file_data_value is not None and not isinstance(file_data_value, str):
                    raise ValidationError(
                        f"File content part at index {index} has invalid 'file.file_data' value.",
                        details={"param": f"{param_prefix}[{index}].file.file_data"},
                    )
                if file_id_value is not None and not isinstance(file_id_value, str):
                    raise ValidationError(
                        f"File content part at index {index} has invalid 'file.file_id' value.",
                        details={"param": f"{param_prefix}[{index}].file.file_id"},
                    )
            validated_parts.append(part)
        return validated_parts
    raise ValidationError(
        "Message content must be string or array of content parts.",
        details={"param": param_prefix},
    )
