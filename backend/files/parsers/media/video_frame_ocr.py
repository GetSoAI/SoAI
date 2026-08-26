"""SoAI - Video frame extraction and OCR [backend/files/parsers/media/video_frame_ocr.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ProcessError, SoAITimeoutError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.parse_execution import raise_if_parse_cancelled, report_parse_progress
from core.files.temp_directory_scope import scoped_temp_directory
from core.files.upload_policy import resolve_temp_directory_runtime
from core.logging.trace import get_logger
from core.media.cancellation import await_media_operation
from core.media.frame_extraction import extract_video_frame
from core.media.frame_geometry import compute_frame_target
from core.media.job_storage import remove_media_file
from core.media.types import OcrFrameText
from core.media.video_frame_sampling import generate_bounded_video_frame_timestamps

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.files.types import ParseExecutionContext
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.media.config import MediaParsingConfig
    from core.media.protocols import MediaOcrRuntimeProtocol
    from core.media.types import VideoProbeResult

__all__ = ("VideoFrameOcrResult", "read_video_ocr_frames")

_FRAME_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ProcessError,
    *RECOVERABLE_EXCEPTIONS,
)
_LOGGER_NAME = "SoAI.files.parsers.video_frame_ocr"
_OPERATION_FRAME_EXTRACTION = "files.parsers.video.frame_extraction"
_RGB_CHANNELS = 3


@dataclass(frozen=True, slots=True)
class VideoFrameOcrResult:
    frames: tuple[OcrFrameText, ...]
    incomplete: bool


async def read_video_ocr_frames(
    *,
    context: ParseExecutionContext,
    probe: VideoProbeResult,
    media_config: MediaParsingConfig,
    config: ConfigProtocol,
    storage_manager: StorageManagerProtocol,
    ocr_runtime: MediaOcrRuntimeProtocol,
) -> VideoFrameOcrResult:
    timestamps = generate_bounded_video_frame_timestamps(
        duration_seconds=probe.duration_seconds,
        frames_per_second=media_config.video_ocr_frames_per_second,
        maximum_frames=media_config.video_ocr_max_frames,
    )
    target = compute_frame_target(
        probe.width,
        probe.height,
        media_config.max_frame_pixels,
    )
    frames: list[OcrFrameText] = []
    incomplete = False
    failure_logged = False
    async with scoped_temp_directory(
        directory=resolve_temp_directory_runtime(config),
        prefix="media-video-ocr-",
        operation_label="media-video-ocr",
    ) as scratch_dir:
        for frame_index, timestamp in enumerate(timestamps):
            raise_if_parse_cancelled(context)
            remaining = context.extraction_deadline - time.monotonic()
            if remaining <= 0:
                raise SoAITimeoutError("Video extraction deadline expired.")
            frame_path = os.path.join(scratch_dir, f"frame-{frame_index:06d}.jpg")
            frame_failed = False
            try:
                estimated_bytes = (
                    target.width
                    * target.height
                    * _RGB_CHANNELS
                    * media_config.temp_reservation_safety_multiplier
                )
                with storage_manager.reserve_disk_space(
                    path=frame_path,
                    required_bytes=estimated_bytes,
                    operation="files.parsers.video.frame",
                    details={"frame_index": frame_index},
                ) as reservation:
                    await await_media_operation(
                        extract_video_frame(
                            source_path=context.source_path,
                            timestamp_seconds=timestamp,
                            target=target,
                            jpeg_quality=media_config.jpeg_quality,
                            output_path=frame_path,
                            timeout_seconds=min(
                                remaining,
                                media_config.frame_extraction_timeout_sec,
                            ),
                        ),
                        context.cancellation_token,
                        extraction_deadline=context.extraction_deadline,
                    )
                    frame_size = await run_joined_thread_call(
                        os.path.getsize,
                        frame_path,
                        task_name="media-video-frame-size",
                    )
                    with reservation.claim_write_bytes(frame_size) as claim:
                        claim.commit()
                    frames.append(
                        await await_media_operation(
                            ocr_runtime.read_frame(
                                frame_path=frame_path,
                                timestamp_seconds=timestamp,
                                timeout_seconds=min(
                                    context.remaining_seconds(),
                                    media_config.ocr_frame_timeout_sec,
                                ),
                            ),
                            context.cancellation_token,
                            extraction_deadline=context.extraction_deadline,
                        ),
                    )
            except _FRAME_FAILURE_EXCEPTIONS as exception:
                if not failure_logged:
                    log_handled_exception(
                        get_logger(_LOGGER_NAME),
                        exception,
                        message="Video frame extraction failed (non-critical).",
                        operation=_OPERATION_FRAME_EXTRACTION,
                        details={
                            "frame_index": frame_index,
                            "timestamp_seconds": timestamp,
                        },
                        level="debug",
                    )
                    failure_logged = True
                frame_failed = True
            finally:
                await run_joined_thread_call(
                    remove_media_file,
                    frame_path,
                    task_name="media-video-frame-remove",
                )
            if frame_failed:
                incomplete = True
            await report_parse_progress(
                context,
                0.45 + ((frame_index + 1) / len(timestamps)) * 0.55,
                "extracting_visible_text",
            )
    return VideoFrameOcrResult(frames=tuple(frames), incomplete=incomplete)
