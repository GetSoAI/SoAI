"""SoAI - OpenAI audio upload payload construction [backend/features/api/routes/openai/audio_upload_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.events.types_models_requests import (
    AudioTranscriptionRequestReceived,
    AudioTranslationRequestReceived,
)
from features.api.routes.multipart_field_values import (
    field_optional_bool,
    field_optional_float,
    field_optional_json,
    field_optional_str,
    field_optional_str_list_alias,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingStagedPart,
    )

__all__ = (
    "OpenAiAudioUploadPayloads",
    "build_openai_audio_upload_payloads",
)


@dataclass(frozen=True, slots=True)
class OpenAiAudioUploadPayloads:
    command_fields: dict[str, JSONValue]
    quota_request_payload: dict[str, JSONValue]


def build_openai_audio_upload_payloads(
    *,
    event_type: type[AudioTranscriptionRequestReceived | AudioTranslationRequestReceived],
    staged_part: StreamingStagedPart,
    fields: dict[str, tuple[str, ...]],
    required_capabilities: tuple[str, ...],
) -> OpenAiAudioUploadPayloads:
    model = field_optional_str(fields, "model")
    if model is None:
        raise ValidationError("Missing required field 'model'.")
    prompt = field_optional_str(fields, "prompt")
    response_format = field_optional_str(fields, "response_format")
    temperature = field_optional_float(fields, "temperature")
    if temperature is not None and (temperature < 0.0 or temperature > 1.0):
        raise ValidationError("Field 'temperature' must be between 0 and 1.")
    temperature_value = float(temperature) if temperature is not None else None
    language = None
    include: tuple[str, ...] = ()
    timestamp_granularities: tuple[str, ...] = ()
    stream: bool | None = None
    chunking_strategy: JSONValue | None = None
    known_speaker_names: tuple[str, ...] = ()
    known_speaker_references: tuple[str, ...] = ()
    if event_type is AudioTranscriptionRequestReceived:
        language = field_optional_str(fields, "language")
        include = field_optional_str_list_alias(fields, key="include", alias_key="include[]")
        if include and any(value != "logprobs" for value in include):
            raise ValidationError("Field 'include' only supports 'logprobs'.")
        timestamp_granularities = field_optional_str_list_alias(
            fields,
            key="timestamp_granularities",
            alias_key="timestamp_granularities[]",
        )
        if timestamp_granularities and any(
            value not in ("word", "segment") for value in timestamp_granularities
        ):
            raise ValidationError(
                "Field 'timestamp_granularities' must contain 'word' and/or 'segment'.",
            )
        stream = field_optional_bool(fields, "stream")
        chunking_raw = field_optional_str(fields, "chunking_strategy")
        if chunking_raw is not None:
            if chunking_raw.strip().startswith("{"):
                chunking_strategy = field_optional_json(fields, "chunking_strategy")
            else:
                chunking_strategy = chunking_raw.strip()
        known_speaker_names = field_optional_str_list_alias(
            fields,
            key="known_speaker_names",
            alias_key="known_speaker_names[]",
        )
        if len(known_speaker_names) > 4:
            raise ValidationError("Field 'known_speaker_names' supports up to 4 items.")
        known_speaker_references = field_optional_str_list_alias(
            fields,
            key="known_speaker_references",
            alias_key="known_speaker_references[]",
        )
        if len(known_speaker_references) > 4:
            raise ValidationError("Field 'known_speaker_references' supports up to 4 items.")
        if (
            known_speaker_names
            and known_speaker_references
            and len(known_speaker_names) != len(known_speaker_references)
        ):
            raise ValidationError(
                "known_speaker_names and known_speaker_references must have the same length.",
            )

    allowed_response_formats = (
        {"json", "text", "srt", "verbose_json", "vtt", "diarized_json"}
        if event_type is AudioTranscriptionRequestReceived
        else {"json", "text", "srt", "verbose_json", "vtt"}
    )
    if response_format is not None and response_format not in allowed_response_formats:
        raise ValidationError("Field 'response_format' has an unsupported value.")
    effective_response_format = response_format or "json"
    if timestamp_granularities and effective_response_format != "verbose_json":
        raise ValidationError(
            "Field 'timestamp_granularities' requires response_format=verbose_json.",
        )
    if include and "logprobs" in include and effective_response_format != "json":
        raise ValidationError("Field 'include=logprobs' requires response_format=json.")

    quota_request_payload: dict[str, JSONValue] = {"model": model}
    if prompt is not None:
        quota_request_payload["prompt"] = prompt

    command_fields: dict[str, JSONValue] = {
        "temp_file_path": staged_part.temp_path,
        "original_filename": staged_part.original_filename,
        "audio_input_bytes": staged_part.size_bytes,
        "required_capabilities": list(required_capabilities),
        "required_modalities": ["audio"],
        "model": model,
    }
    if prompt is not None:
        command_fields["prompt"] = prompt
    if response_format is not None:
        command_fields["response_format"] = response_format
    if temperature_value is not None:
        command_fields["temperature"] = temperature_value
    if language is not None:
        command_fields["language"] = language
    if include:
        command_fields["include"] = list(include)
    if timestamp_granularities:
        command_fields["timestamp_granularities"] = list(timestamp_granularities)
    if stream is not None:
        command_fields["stream"] = stream
    if chunking_strategy is not None:
        command_fields["chunking_strategy"] = chunking_strategy
    if known_speaker_names:
        command_fields["known_speaker_names"] = list(known_speaker_names)
    if known_speaker_references:
        command_fields["known_speaker_references"] = list(known_speaker_references)
    return OpenAiAudioUploadPayloads(
        command_fields=command_fields,
        quota_request_payload=quota_request_payload,
    )
