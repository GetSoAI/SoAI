"""SoAI - Whisper media IPC worker entrypoint [backend/core/media/transcription_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ServiceUnavailableError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.ipc.ndjson_rpc_loop import NdjsonRpcRequest, NdjsonRpcResponse
from core.logging.trace import get_logger
from core.media.whisper_worker_runtime import transcribe_audio_chunk
from core.media.worker_runtime import run_media_worker_session
from core.runtime.environment_flags import is_soai_stay_offline
from core.runtime.network_policy import OfflineModeError
from core.runtime.worker_entrypoint import run_worker_entrypoint
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("main",)

LOGGER_NAME = "SoAI.core.media.transcription_worker"
OPERATION = "core.media.transcription_worker.transcribe"


def _required_text(value: JSONValue, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name} must be a non-empty string.")
    return value.strip()


async def _handle_request(request: NdjsonRpcRequest) -> NdjsonRpcResponse:
    payload = request.payload
    if request.method != "transcribe_chunk" or not isinstance(payload, dict):
        return NdjsonRpcResponse(request.request_id, False, {"error": "invalid_request"})
    try:
        result = transcribe_audio_chunk(
            file_path=_required_text(payload.get("file_path"), "file_path"),
            model_name=_required_text(payload.get("model"), "model"),
            language=coerce_optional_trimmed_str(payload.get("language")),
            task=_required_text(payload.get("task"), "task"),
            include_word_timestamps=payload.get("include_word_timestamps") is True,
            offline_mode=(payload.get("offline_mode") is True or is_soai_stay_offline()),
        )
        return NdjsonRpcResponse(request.request_id, True, result)
    except OfflineModeError as exception:
        return NdjsonRpcResponse(
            request.request_id,
            False,
            {"error": "offline_mode", "message": str(exception)},
        )
    except (ValidationError, ServiceUnavailableError) as exception:
        return NdjsonRpcResponse(
            request.request_id,
            False,
            {"error": str(exception.code), "message": exception.message},
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        error = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Media transcription request failed.",
            operation=OPERATION,
            level="warning",
        )
        return NdjsonRpcResponse(
            request.request_id,
            False,
            {"error": "transcription_failed", "message": "Media transcription failed."},
        )


async def _run() -> None:
    await run_media_worker_session(
        worker_label="media transcription worker",
        handle_request=_handle_request,
    )


def main() -> None:
    run_worker_entrypoint(
        _run(),
        logger=get_logger(LOGGER_NAME),
        unhandled_message="Media transcription worker failed.",
        operation=OPERATION,
    )


if __name__ == "__main__":
    main()
