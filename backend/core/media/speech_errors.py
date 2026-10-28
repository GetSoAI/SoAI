"""SoAI - Speech-to-text setup and option failure types [backend/core/media/speech_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "SETUP_CANDIDATES_DETAIL_KEY",
    "SPEECH_TO_TEXT_CAPABILITY",
    "TRANSCRIPTION_MODEL_UNAVAILABLE_CODE",
    "TRANSCRIPTION_OPTION_UNSUPPORTED_CODE",
    "SpeechToTextUnavailableError",
    "TranscriptionOptionUnsupportedError",
    "build_speech_unavailable_error",
    "build_transcription_option_error",
    "without_setup_candidates",
)

SPEECH_TO_TEXT_CAPABILITY = "speech_to_text"
TRANSCRIPTION_MODEL_UNAVAILABLE_CODE = "transcription_model_unavailable"
TRANSCRIPTION_OPTION_UNSUPPORTED_CODE = "transcription_option_unsupported"
SETUP_CANDIDATES_DETAIL_KEY = "setup"


class SpeechToTextUnavailableError(ValidationError):
    code: str | int = TRANSCRIPTION_MODEL_UNAVAILABLE_CODE
    http_status = 400

    @property
    def reason(self) -> str:
        value = (self.details or {}).get("reason")
        return value if isinstance(value, str) else ""


def build_speech_unavailable_error(
    message: str, *, reason: str, public_details: JSONDict
) -> SpeechToTextUnavailableError:
    error = SpeechToTextUnavailableError(message, details={"reason": reason})
    apply_public_error_payload(
        error,
        ErrorPublicPayload(
            code=TRANSCRIPTION_MODEL_UNAVAILABLE_CODE,
            message=message,
            details=public_details,
            http_status=400,
        ),
    )
    return error


def without_setup_candidates(error: SpeechToTextUnavailableError) -> SpeechToTextUnavailableError:
    details = dict(error.public_details or {})
    details.pop(SETUP_CANDIDATES_DETAIL_KEY, None)
    return build_speech_unavailable_error(
        "Local speech-to-text is unavailable. Ask an administrator to set up a speech backend and model.",
        reason=error.reason,
        public_details=details,
    )


class TranscriptionOptionUnsupportedError(ValidationError):
    code: str | int = TRANSCRIPTION_OPTION_UNSUPPORTED_CODE
    http_status = 400


def build_transcription_option_error(
    message: str, *, model: str, param: str | None
) -> TranscriptionOptionUnsupportedError:
    error = TranscriptionOptionUnsupportedError(message, details={"model": model, "param": param})
    apply_public_error_payload(
        error,
        ErrorPublicPayload(
            code=TRANSCRIPTION_OPTION_UNSUPPORTED_CODE,
            message=message,
            param=param,
            details={"reason": "unsupported_option", "model": model},
            http_status=400,
        ),
    )
    return error
