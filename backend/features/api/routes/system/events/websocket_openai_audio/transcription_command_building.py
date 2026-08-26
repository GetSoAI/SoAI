"""SoAI - WebSocket OpenAI transcription command building [backend/features/api/routes/system/events/websocket_openai_audio/transcription_command_building.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from math import isfinite

from core.errors.exceptions import ValidationError
from core.events.types_base import Event
from core.events.types_models_requests import AudioTranscriptionRequestReceived
from core.runtime.request_context import RequestContext
from core.types.json import JSONDict, JSONValue, is_json_dict, is_str_list
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "build_audio_transcription_request_received",
    "reject_webui_transcription_stream_field",
)


def reject_webui_transcription_stream_field(
    command_fields: Mapping[str, JSONValue],
) -> None:
    if "stream" in command_fields:
        raise ValidationError("WebUI transcription does not accept stream.")


def build_audio_transcription_request_received(
    *,
    reply_queue: asyncio.Queue[Event],
    context: RequestContext,
    command_fields: Mapping[str, JSONValue],
) -> AudioTranscriptionRequestReceived:
    temp_file_path_value = command_fields.get("temp_file_path")
    if not isinstance(temp_file_path_value, str) or not temp_file_path_value:
        raise ValidationError("Invalid transcription temp_file_path.")
    original_filename_value = command_fields.get("original_filename")
    if not isinstance(original_filename_value, str) or not original_filename_value:
        raise ValidationError("Invalid transcription original_filename.")
    model = coerce_optional_trimmed_str(command_fields.get("model"))
    prompt_value = command_fields.get("prompt")
    prompt = prompt_value if isinstance(prompt_value, str) and prompt_value else None
    response_format = coerce_optional_trimmed_str(command_fields.get("response_format"))
    temperature_value = command_fields.get("temperature")
    if temperature_value is None:
        temperature = None
    else:
        if isinstance(temperature_value, bool):
            raise ValidationError("Invalid transcription temperature.")
        if not isinstance(temperature_value, int | float):
            raise ValidationError("Invalid transcription temperature.")
        temperature = float(temperature_value)
        if not isfinite(temperature) or temperature < 0.0 or temperature > 1.0:
            raise ValidationError("Invalid transcription temperature.")
    language_value = command_fields.get("language")
    language = language_value if isinstance(language_value, str) and language_value else None
    include_value = command_fields.get("include")
    include: list[str] | None
    if include_value is None:
        include = None
    elif is_str_list(include_value):
        include = include_value
    else:
        raise ValidationError("Invalid transcription include.")
    timestamp_granularities_value = command_fields.get("timestamp_granularities")
    timestamp_granularities: list[str] | None
    if timestamp_granularities_value is None:
        timestamp_granularities = None
    elif is_str_list(timestamp_granularities_value):
        timestamp_granularities = timestamp_granularities_value
    else:
        raise ValidationError("Invalid transcription timestamp_granularities.")
    reject_webui_transcription_stream_field(command_fields)
    chunking_strategy_value = command_fields.get("chunking_strategy")
    chunking_strategy: JSONDict | str | None
    if chunking_strategy_value is None:
        chunking_strategy = None
    elif (isinstance(chunking_strategy_value, str) and chunking_strategy_value) or is_json_dict(
        chunking_strategy_value
    ):
        chunking_strategy = chunking_strategy_value
    else:
        raise ValidationError("Invalid transcription chunking_strategy.")
    known_speaker_names_value = command_fields.get("known_speaker_names")
    known_speaker_names: list[str] | None
    if known_speaker_names_value is None:
        known_speaker_names = None
    elif is_str_list(known_speaker_names_value):
        known_speaker_names = known_speaker_names_value
    else:
        raise ValidationError("Invalid transcription known_speaker_names.")
    known_speaker_references_value = command_fields.get("known_speaker_references")
    known_speaker_references: list[str] | None
    if known_speaker_references_value is None:
        known_speaker_references = None
    elif is_str_list(known_speaker_references_value):
        known_speaker_references = known_speaker_references_value
    else:
        raise ValidationError("Invalid transcription known_speaker_references.")
    required_capabilities_value = command_fields.get("required_capabilities")
    if not is_str_list(required_capabilities_value):
        raise ValidationError("Invalid transcription required_capabilities.")
    required_capabilities = tuple(required_capabilities_value)
    required_modalities_value = command_fields.get("required_modalities")
    if not is_str_list(required_modalities_value):
        raise ValidationError("Invalid transcription required_modalities.")
    required_modalities = tuple(required_modalities_value)
    return AudioTranscriptionRequestReceived(
        reply_channel=reply_queue,
        context=context,
        temp_file_path=temp_file_path_value,
        original_filename=original_filename_value,
        model=model,
        language=language,
        prompt=prompt,
        response_format=response_format,
        temperature=temperature,
        include=include,
        timestamp_granularities=timestamp_granularities,
        stream=None,
        chunking_strategy=chunking_strategy,
        known_speaker_names=known_speaker_names,
        known_speaker_references=known_speaker_references,
        required_capabilities=required_capabilities,
        required_modalities=required_modalities,
    )
