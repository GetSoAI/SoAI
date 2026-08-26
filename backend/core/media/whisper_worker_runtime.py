"""SoAI - Whisper chunk transcription worker runtime [backend/core/media/whisper_worker_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
from functools import lru_cache
from typing import TYPE_CHECKING

import whisper

from core.errors.exceptions import ServiceUnavailableError, ValidationError
from core.runtime.network_policy import OfflineModeError
from core.types.json import is_json_dict
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from whisper import Whisper

    from core.types.json import JSONDict

__all__ = ("FFMPEG_BINARY_NAME", "transcribe_audio_chunk")

FFMPEG_BINARY_NAME = "ffmpeg"


def _model_cache_path(model_name: str) -> str:
    normalized = coerce_optional_trimmed_str(model_name)
    if (
        normalized is None
        or os.path.sep in normalized
        or (os.path.altsep and os.path.altsep in normalized)
    ):
        raise ValidationError("Whisper model name is invalid.")
    if normalized not in tuple(whisper.available_models()):
        raise ValidationError(f"Unknown Whisper model: {normalized}")
    cache_root = os.path.join(
        os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
        "whisper",
    )
    return os.path.join(cache_root, f"{normalized}.pt")


@lru_cache(maxsize=8)
def _load_model(model_name: str) -> Whisper:
    return whisper.load_model(model_name)


def transcribe_audio_chunk(
    *,
    file_path: str,
    model_name: str,
    language: str | None,
    task: str,
    include_word_timestamps: bool,
    offline_mode: bool,
) -> JSONDict:
    if shutil.which(FFMPEG_BINARY_NAME) is None:
        raise ServiceUnavailableError("Audio transcription requires ffmpeg.")
    if offline_mode and not os.path.isfile(_model_cache_path(model_name)):
        raise OfflineModeError("The selected Whisper model is not available offline.")
    options: dict[str, str | float | bool] = {
        "task": task,
        "temperature": 0.0,
        "condition_on_previous_text": False,
        "word_timestamps": include_word_timestamps,
    }
    if language is not None:
        options["language"] = language
    result = _load_model(model_name).transcribe(file_path, **options)
    if not is_json_dict(result):
        raise ValidationError("Whisper returned an invalid transcription payload.")
    text = result.get("text")
    detected_language = result.get("language")
    segments = result.get("segments")
    return {
        "text": text if isinstance(text, str) else "",
        "language": detected_language if isinstance(detected_language, str) else None,
        "segments": segments if isinstance(segments, list) else [],
    }
