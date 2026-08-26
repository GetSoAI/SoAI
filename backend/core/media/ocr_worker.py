"""SoAI - Managed video frame OCR worker entrypoint [backend/core/media/ocr_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.ipc.ndjson_rpc_loop import NdjsonRpcRequest, NdjsonRpcResponse
from core.logging.trace import get_logger
from core.media.ocr_engine import ocr_image_file
from core.media.worker_runtime import run_media_worker_session
from core.runtime.worker_entrypoint import run_worker_entrypoint

__all__ = ("main",)

LOGGER_NAME = "SoAI.core.media.ocr_worker"
OPERATION = "core.media.ocr_worker.read_frame"


async def _handle_request(request: NdjsonRpcRequest) -> NdjsonRpcResponse:
    payload = request.payload
    if request.method != "read_frame" or not isinstance(payload, dict):
        return NdjsonRpcResponse(
            request_id=request.request_id,
            ok=False,
            payload={"error": "invalid_request", "message": "Invalid OCR request."},
        )
    frame_path = payload.get("frame_path")
    if not isinstance(frame_path, str) or not frame_path:
        return NdjsonRpcResponse(
            request_id=request.request_id,
            ok=False,
            payload={"error": "invalid_request", "message": "Frame path is required."},
        )
    try:
        text, confidence = ocr_image_file(frame_path)
        return NdjsonRpcResponse(
            request_id=request.request_id,
            ok=True,
            payload={"text": text, "confidence": confidence},
        )
    except ValidationError as exception:
        return NdjsonRpcResponse(
            request_id=request.request_id,
            ok=False,
            payload={"error": "invalid_frame", "message": exception.message},
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        error = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Video frame OCR request failed.",
            operation=OPERATION,
            level="warning",
        )
        return NdjsonRpcResponse(
            request_id=request.request_id,
            ok=False,
            payload={"error": "ocr_failed", "message": "Video frame OCR failed."},
        )


async def _run() -> None:
    await run_media_worker_session(
        worker_label="media OCR worker",
        handle_request=_handle_request,
    )


def main() -> None:
    run_worker_entrypoint(
        _run(),
        logger=get_logger(LOGGER_NAME),
        unhandled_message="Media OCR worker failed.",
        operation=OPERATION,
    )


if __name__ == "__main__":
    main()
