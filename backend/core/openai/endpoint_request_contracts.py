"""SoAI - OpenAI endpoint request contract resolution [backend/core/openai/endpoint_request_contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.errors.exceptions import StateError
from core.openai.openai_current import (
    CHAT_COMPLETIONS_CREATE_FIELDS,
    CHAT_COMPLETIONS_MODIFY_FIELDS,
    COMPLETIONS_CREATE_FIELDS,
    EMBEDDINGS_CREATE_FIELDS,
    RESPONSES_COMPACT_FIELDS,
    RESPONSES_CREATE_FIELDS,
    RESPONSES_INPUT_TOKENS_FIELDS,
)
from core.openai.openai_current_media import (
    AUDIO_SPEECH_CREATE_FIELDS,
    AUDIO_TRANSCRIPTIONS_CREATE_MULTIPART_FIELDS,
    AUDIO_TRANSLATIONS_CREATE_MULTIPART_FIELDS,
    FILES_CREATE_MULTIPART_FIELDS,
    IMAGES_EDITS_CREATE_MULTIPART_FIELDS,
    IMAGES_GENERATIONS_CREATE_FIELDS,
    IMAGES_VARIATIONS_CREATE_MULTIPART_FIELDS,
)
from core.openai.upstream_request_customization import SOAI_INTERNAL_OPENAI_REQUEST_KEYS

__all__ = (
    "SOAI_INTERNAL_OPENAI_REQUEST_KEYS",
    "OpenAIEndpointFamily",
    "OpenAIRequestBodyContract",
    "OpenAIRequestBodyOperation",
    "contract_for_openai_request_body_operation",
)


class OpenAIEndpointFamily(str, Enum):
    CHAT_COMPLETIONS = "chat_completions"
    COMPLETIONS = "completions"
    RESPONSES = "responses"
    EMBEDDINGS = "embeddings"
    IMAGES = "images"
    AUDIO = "audio"
    FILES = "files"


class OpenAIRequestBodyOperation(str, Enum):
    CHAT_COMPLETIONS_CREATE = "chat_completions_create"
    CHAT_COMPLETIONS_MODIFY = "chat_completions_modify"
    COMPLETIONS_CREATE = "completions_create"
    RESPONSES_CREATE = "responses_create"
    RESPONSES_INPUT_TOKENS = "responses_input_tokens"
    RESPONSES_COMPACT = "responses_compact"
    EMBEDDINGS_CREATE = "embeddings_create"
    IMAGES_GENERATIONS_CREATE = "images_generations_create"
    IMAGES_EDITS_CREATE_MULTIPART = "images_edits_create_multipart"
    IMAGES_VARIATIONS_CREATE_MULTIPART = "images_variations_create_multipart"
    AUDIO_TRANSCRIPTIONS_CREATE_MULTIPART = "audio_transcriptions_create_multipart"
    AUDIO_TRANSLATIONS_CREATE_MULTIPART = "audio_translations_create_multipart"
    AUDIO_SPEECH_CREATE = "audio_speech_create"
    FILES_CREATE_MULTIPART = "files_create_multipart"


@dataclass(frozen=True, slots=True)
class OpenAIRequestBodyContract:
    official_fields: frozenset[str]
    endpoint_family: OpenAIEndpointFamily


def contract_for_openai_request_body_operation(
    operation: OpenAIRequestBodyOperation,
) -> OpenAIRequestBodyContract:
    official_fields = _official_fields_for_operation(operation)
    endpoint_family = _endpoint_family_for_operation(operation)
    return OpenAIRequestBodyContract(
        official_fields=official_fields,
        endpoint_family=endpoint_family,
    )


def _endpoint_family_for_operation(
    operation: OpenAIRequestBodyOperation,
) -> OpenAIEndpointFamily:
    match operation:
        case OpenAIRequestBodyOperation.CHAT_COMPLETIONS_CREATE:
            return OpenAIEndpointFamily.CHAT_COMPLETIONS
        case OpenAIRequestBodyOperation.CHAT_COMPLETIONS_MODIFY:
            return OpenAIEndpointFamily.CHAT_COMPLETIONS
        case OpenAIRequestBodyOperation.COMPLETIONS_CREATE:
            return OpenAIEndpointFamily.COMPLETIONS
        case OpenAIRequestBodyOperation.RESPONSES_CREATE:
            return OpenAIEndpointFamily.RESPONSES
        case OpenAIRequestBodyOperation.RESPONSES_INPUT_TOKENS:
            return OpenAIEndpointFamily.RESPONSES
        case OpenAIRequestBodyOperation.RESPONSES_COMPACT:
            return OpenAIEndpointFamily.RESPONSES
        case OpenAIRequestBodyOperation.EMBEDDINGS_CREATE:
            return OpenAIEndpointFamily.EMBEDDINGS
        case OpenAIRequestBodyOperation.IMAGES_GENERATIONS_CREATE:
            return OpenAIEndpointFamily.IMAGES
        case OpenAIRequestBodyOperation.IMAGES_EDITS_CREATE_MULTIPART:
            return OpenAIEndpointFamily.IMAGES
        case OpenAIRequestBodyOperation.IMAGES_VARIATIONS_CREATE_MULTIPART:
            return OpenAIEndpointFamily.IMAGES
        case OpenAIRequestBodyOperation.AUDIO_TRANSCRIPTIONS_CREATE_MULTIPART:
            return OpenAIEndpointFamily.AUDIO
        case OpenAIRequestBodyOperation.AUDIO_TRANSLATIONS_CREATE_MULTIPART:
            return OpenAIEndpointFamily.AUDIO
        case OpenAIRequestBodyOperation.AUDIO_SPEECH_CREATE:
            return OpenAIEndpointFamily.AUDIO
        case OpenAIRequestBodyOperation.FILES_CREATE_MULTIPART:
            return OpenAIEndpointFamily.FILES
    raise StateError(f"Unhandled OpenAI request body operation family: {operation!r}")


def _official_fields_for_operation(operation: OpenAIRequestBodyOperation) -> frozenset[str]:
    match operation:
        case OpenAIRequestBodyOperation.CHAT_COMPLETIONS_CREATE:
            return CHAT_COMPLETIONS_CREATE_FIELDS
        case OpenAIRequestBodyOperation.CHAT_COMPLETIONS_MODIFY:
            return CHAT_COMPLETIONS_MODIFY_FIELDS
        case OpenAIRequestBodyOperation.COMPLETIONS_CREATE:
            return COMPLETIONS_CREATE_FIELDS
        case OpenAIRequestBodyOperation.RESPONSES_CREATE:
            return RESPONSES_CREATE_FIELDS
        case OpenAIRequestBodyOperation.RESPONSES_INPUT_TOKENS:
            return RESPONSES_INPUT_TOKENS_FIELDS
        case OpenAIRequestBodyOperation.RESPONSES_COMPACT:
            return RESPONSES_COMPACT_FIELDS
        case OpenAIRequestBodyOperation.EMBEDDINGS_CREATE:
            return EMBEDDINGS_CREATE_FIELDS
        case OpenAIRequestBodyOperation.IMAGES_GENERATIONS_CREATE:
            return IMAGES_GENERATIONS_CREATE_FIELDS
        case OpenAIRequestBodyOperation.IMAGES_EDITS_CREATE_MULTIPART:
            return IMAGES_EDITS_CREATE_MULTIPART_FIELDS
        case OpenAIRequestBodyOperation.IMAGES_VARIATIONS_CREATE_MULTIPART:
            return IMAGES_VARIATIONS_CREATE_MULTIPART_FIELDS
        case OpenAIRequestBodyOperation.AUDIO_TRANSCRIPTIONS_CREATE_MULTIPART:
            return AUDIO_TRANSCRIPTIONS_CREATE_MULTIPART_FIELDS
        case OpenAIRequestBodyOperation.AUDIO_TRANSLATIONS_CREATE_MULTIPART:
            return AUDIO_TRANSLATIONS_CREATE_MULTIPART_FIELDS
        case OpenAIRequestBodyOperation.AUDIO_SPEECH_CREATE:
            return AUDIO_SPEECH_CREATE_FIELDS
        case OpenAIRequestBodyOperation.FILES_CREATE_MULTIPART:
            return FILES_CREATE_MULTIPART_FIELDS
    raise StateError(f"Unhandled OpenAI request body operation: {operation!r}")
