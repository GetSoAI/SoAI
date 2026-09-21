"""SoAI - Bounded provider video frame projection [backend/features/api/runtime/webui_attachments/provider_video_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import SoAIError
from core.files.temp_directory_scope import scoped_temp_directory
from core.files.upload_policy import resolve_temp_directory_runtime
from core.media.frame_extraction import extract_video_frame
from core.media.frame_geometry import compute_frame_target
from core.media.probing import probe_video
from core.media.video_frame_sampling import generate_bounded_video_frame_timestamps
from core.types.json_value import copy_json_dict_list
from features.api.runtime.webui_attachments.provider_image_projection import (
    shape_descriptor_image_for_provider,
)

if TYPE_CHECKING:
    from typing import Literal

    from core.config.protocols import ConfigProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.types.json import JSONDict
    from features.api.runtime.webui_attachments.provider_video_budget import (
        ProviderVideoAllocation,
    )
    from features.api.runtime.webui_attachments.provider_video_settings import (
        ProviderVideoSettings,
    )

    type ProviderVideoProjectionStatus = Literal["complete", "degraded", "failed"]

__all__ = ("ProviderVideoProjection", "project_video_snapshot_for_provider")

_FRAME_CADENCE_PER_SECOND = 1.0
_ESTIMATED_RGB_CHANNELS = 3


@dataclass(frozen=True, slots=True)
class ProviderVideoProjection:
    status: ProviderVideoProjectionStatus
    parts: tuple[JSONDict, ...]
    sampled_frames: int
    projected_frames: int
    reason: str | None

    def copy_parts(self) -> list[JSONDict]:
        return copy_json_dict_list(list(self.parts))

    def copy(self) -> ProviderVideoProjection:
        return ProviderVideoProjection(
            status=self.status,
            parts=tuple(self.copy_parts()),
            sampled_frames=self.sampled_frames,
            projected_frames=self.projected_frames,
            reason=self.reason,
        )


def _timestamp_label(
    timestamp_seconds: float,
    *,
    frame_number: int,
    frame_count: int,
) -> str:
    milliseconds = max(0, round(timestamp_seconds * 1000.0))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, remaining_milliseconds = divmod(remainder, 1000)
    timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{remaining_milliseconds:03d}"
    return f"Video frame {frame_number}/{frame_count} at {timestamp}"


def _encoded_chars(part: JSONDict) -> int:
    image_url = part.get("image_url")
    url = image_url.get("url") if isinstance(image_url, dict) else None
    if not isinstance(url, str):
        return 0
    separator_index = url.find(",")
    return len(url) if separator_index < 0 else len(url) - separator_index - 1


async def _shape_frame(
    *,
    frame_path: str,
    config: ConfigProtocol,
    max_encoded_chars: int,
) -> JSONDict | None:
    descriptor = os.open(frame_path, os.O_RDONLY)
    try:
        image_shaper = partial(
            shape_descriptor_image_for_provider,
            descriptor=descriptor,
            declared_content_type="image/jpeg",
            config=config,
            max_encoded_chars=max_encoded_chars,
        )
        shaped = await run_joined_thread_call(
            image_shaper,
            task_name="provider-video-frame-image-shape",
        )
    finally:
        os.close(descriptor)
    return shaped.part


async def _extract_frame(
    *,
    source_path: str,
    frame_path: str,
    timestamp_seconds: float,
    width: int,
    height: int,
    timeout_seconds: float,
    config: ConfigProtocol,
    storage_manager: StorageManagerProtocol,
) -> None:
    max_pixels = config.get_int("SERVER.WEBUI.PROVIDER_IMAGE.MAX_PIXELS")
    target = compute_frame_target(width, height, max_pixels)
    estimated_bytes = target.width * target.height * _ESTIMATED_RGB_CHANNELS
    with storage_manager.reserve_disk_space(
        path=frame_path,
        required_bytes=estimated_bytes,
        operation="webui.attachments.provider_video.frame",
        details={"timestamp_seconds": timestamp_seconds},
    ) as reservation:
        await extract_video_frame(
            source_path=source_path,
            timestamp_seconds=timestamp_seconds,
            target=target,
            jpeg_quality=config.get_int("SERVER.WEBUI.PROVIDER_IMAGE.JPEG_QUALITY"),
            output_path=frame_path,
            timeout_seconds=timeout_seconds,
        )
        frame_size = await run_joined_thread_call(
            os.path.getsize,
            frame_path,
            task_name="provider-video-frame-size",
        )
        with reservation.claim_write_bytes(frame_size) as claim:
            claim.commit()


def _result(
    *,
    parts: list[JSONDict],
    sampled_frames: int,
    projected_frames: int,
    reason: str | None,
) -> ProviderVideoProjection:
    if projected_frames == sampled_frames and reason is None:
        status: ProviderVideoProjectionStatus = "complete"
    elif projected_frames > 0:
        status = "degraded"
    else:
        status = "failed"
    return ProviderVideoProjection(
        status=status,
        parts=tuple(copy_json_dict_list(parts)),
        sampled_frames=sampled_frames,
        projected_frames=projected_frames,
        reason=reason,
    )


async def _project_with_deadline(
    *,
    source_path: str,
    allocation: ProviderVideoAllocation,
    settings: ProviderVideoSettings,
    config: ConfigProtocol,
    storage_manager: StorageManagerProtocol,
) -> ProviderVideoProjection:
    deadline = time.monotonic() + settings.projection_timeout_sec
    probe = await probe_video(
        source_path,
        timeout_seconds=max(0.001, deadline - time.monotonic()),
    )
    timestamps = generate_bounded_video_frame_timestamps(
        duration_seconds=probe.duration_seconds,
        frames_per_second=_FRAME_CADENCE_PER_SECOND,
        maximum_frames=allocation.maximum_frames,
    )
    parts: list[JSONDict] = []
    projected_frames = 0
    remaining_chars = allocation.maximum_encoded_chars
    frame_failure = False
    async with scoped_temp_directory(
        directory=resolve_temp_directory_runtime(config),
        prefix="provider-video-",
        operation_label="provider-video-projection",
    ) as scratch_dir:
        for frame_index, timestamp_seconds in enumerate(timestamps):
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0.0:
                return _result(
                    parts=parts,
                    sampled_frames=len(timestamps),
                    projected_frames=projected_frames,
                    reason="Video frame projection timed out.",
                )
            frame_path = os.path.join(scratch_dir, f"frame-{frame_index:06d}.jpg")
            try:
                await _extract_frame(
                    source_path=source_path,
                    frame_path=frame_path,
                    timestamp_seconds=timestamp_seconds,
                    width=probe.width,
                    height=probe.height,
                    timeout_seconds=remaining_seconds,
                    config=config,
                    storage_manager=storage_manager,
                )
                image_part = await _shape_frame(
                    frame_path=frame_path,
                    config=config,
                    max_encoded_chars=remaining_chars,
                )
            except (OSError, SoAIError):
                frame_failure = True
                continue
            if image_part is None:
                frame_failure = True
                continue
            encoded_chars = _encoded_chars(image_part)
            if encoded_chars <= 0 or encoded_chars > remaining_chars:
                frame_failure = True
                continue
            remaining_chars -= encoded_chars
            projected_frames += 1
            parts.extend(
                (
                    {
                        "type": "text",
                        "text": _timestamp_label(
                            timestamp_seconds,
                            frame_number=frame_index + 1,
                            frame_count=len(timestamps),
                        ),
                    },
                    image_part,
                ),
            )
    reason = "Some video frames were unavailable." if frame_failure else None
    return _result(
        parts=parts,
        sampled_frames=len(timestamps),
        projected_frames=projected_frames,
        reason=reason,
    )


async def project_video_snapshot_for_provider(
    *,
    source_path: str,
    allocation: ProviderVideoAllocation,
    settings: ProviderVideoSettings,
    config: ConfigProtocol,
    storage_manager: StorageManagerProtocol,
    semaphore: asyncio.Semaphore,
) -> ProviderVideoProjection:
    try:
        async with asyncio.timeout(settings.projection_timeout_sec):
            async with semaphore:
                return await _project_with_deadline(
                    source_path=source_path,
                    allocation=allocation,
                    settings=settings,
                    config=config,
                    storage_manager=storage_manager,
                )
    except TimeoutError:
        return _result(
            parts=[],
            sampled_frames=allocation.maximum_frames,
            projected_frames=0,
            reason="Video frame projection timed out.",
        )
    except (OSError, SoAIError):
        return _result(
            parts=[],
            sampled_frames=allocation.maximum_frames,
            projected_frames=0,
            reason="Video frames were unavailable.",
        )
