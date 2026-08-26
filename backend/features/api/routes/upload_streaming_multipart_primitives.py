"""SoAI - Multipart parsing primitives and queue helpers [backend/features/api/routes/upload_streaming_multipart_primitives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import queue
from dataclasses import dataclass
from typing import TYPE_CHECKING

from python_multipart.multipart import parse_options_header

from core.errors.exceptions import ValidationError
from features.api.routes.internal_protocols import (
    MultipartBytesReporter,
    MultipartFieldReporter,
    MultipartFileStartReporter,
)
from features.api.routes.upload_streaming_multipart_models import StreamingMultipartSpec

if TYPE_CHECKING:
    from fastapi import Request

__all__ = (
    "BytesProgressEvent",
    "FieldProgressEvent",
    "FileStartProgressEvent",
    "drain_and_signal_queue",
    "drain_progress_events",
    "ensure_dir_exists",
    "require_multipart_boundary",
    "validate_spec",
)


@dataclass(frozen=True, slots=True)
class BytesProgressEvent:
    bytes_done: int


@dataclass(frozen=True, slots=True)
class FieldProgressEvent:
    field_name: str
    field_value: str


@dataclass(frozen=True, slots=True)
class FileStartProgressEvent:
    filename: str


def ensure_dir_exists(path: str) -> None:
    if not os.path.isdir(path):
        raise ValidationError("Upload temp directory does not exist.")


def require_multipart_boundary(request: Request) -> tuple[str, bytes]:
    raw = request.headers.get("content-type")
    if not raw:
        raise ValidationError("Missing Content-Type.")
    media_type, options = parse_options_header(raw)
    if media_type.lower() != b"multipart/form-data":
        raise ValidationError("Content-Type must be multipart/form-data.")
    boundary = options.get(b"boundary")
    if not boundary:
        raise ValidationError("Missing multipart boundary.")
    return "multipart/form-data", boundary


def validate_spec(spec: StreamingMultipartSpec) -> None:
    if not spec.required_fields.issubset(spec.allowed_fields):
        raise ValidationError("Required metadata fields must be included in allowed_fields.")
    if not spec.allowed_file_fields:
        raise ValidationError("At least one allowed file field must be configured.")
    if not spec.required_file_fields:
        raise ValidationError("At least one required file field must be configured.")
    if not spec.required_file_fields.issubset(spec.allowed_file_fields):
        raise ValidationError("Required file fields must be included in allowed_file_fields.")
    if spec.max_file_bytes is not None and spec.max_file_bytes <= 0:
        raise ValidationError("max_file_bytes must be a positive integer.")
    if spec.max_total_file_bytes is not None and spec.max_total_file_bytes <= 0:
        raise ValidationError("max_total_file_bytes must be a positive integer when provided.")
    if spec.max_field_bytes <= 0:
        raise ValidationError("max_field_bytes must be a positive integer.")
    if spec.max_total_field_bytes <= 0:
        raise ValidationError("max_total_field_bytes must be a positive integer.")


def drain_and_signal_queue(target_queue: queue.Queue[bytes | None]) -> bool:
    while True:
        try:
            target_queue.get_nowait()
        except queue.Empty:
            break
    try:
        target_queue.put_nowait(None)
        return True
    except queue.Full:
        return False


def drain_progress_events(
    progress_queue: queue.SimpleQueue[
        BytesProgressEvent | FieldProgressEvent | FileStartProgressEvent
    ],
    *,
    report_bytes: MultipartBytesReporter,
    report_field: MultipartFieldReporter | None,
    report_file_start: MultipartFileStartReporter | None,
) -> None:
    while True:
        try:
            event = progress_queue.get_nowait()
        except queue.Empty:
            return
        if isinstance(event, BytesProgressEvent):
            report_bytes(event.bytes_done)
            continue
        if isinstance(event, FieldProgressEvent):
            if report_field is not None:
                report_field(event.field_name, event.field_value)
            continue
        if report_file_start is not None:
            report_file_start(event.filename)
