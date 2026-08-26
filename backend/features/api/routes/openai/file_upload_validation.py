"""SoAI - OpenAI file upload field validation [backend/features/api/routes/openai/file_upload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.errors.exceptions import ValidationError
from features.api.routes.multipart_field_values import (
    field_optional_int,
    field_optional_json_object,
    field_optional_str,
    field_required_str,
)
from features.api.routes.openai.streaming_upload_error_handling import (
    finalize_cleanup_and_raise_invalid_request,
)

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryLifecycleView
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingMultipartResult,
    )

__all__ = ("validate_file_upload_fields",)

_FILE_UPLOAD_EXPIRES_MIN_SECONDS = 3_600
_FILE_UPLOAD_EXPIRES_MAX_SECONDS = 2_592_000


async def validate_file_upload_fields(
    request: Request,
    *,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    parsed: StreamingMultipartResult,
    staged_paths: list[str],
) -> tuple[str, str | None, int | None]:
    try:
        purpose = field_required_str(parsed.fields, "purpose")
    except ValidationError as exception:
        await finalize_cleanup_and_raise_invalid_request(
            request,
            registry=registry,
            task_id=task_id,
            error_message=str(exception),
            staged_paths=staged_paths,
        )
    try:
        expires_anchor = field_optional_str(parsed.fields, "expires_after[anchor]")
        expires_seconds = field_optional_int(parsed.fields, "expires_after[seconds]")
        expires_after_raw = field_optional_str(parsed.fields, "expires_after")
    except ValidationError as exception:
        await finalize_cleanup_and_raise_invalid_request(
            request,
            registry=registry,
            task_id=task_id,
            error_message=str(exception),
            staged_paths=staged_paths,
        )
    if expires_after_raw is not None and (
        expires_anchor is not None or expires_seconds is not None
    ):
        await finalize_cleanup_and_raise_invalid_request(
            request,
            registry=registry,
            task_id=task_id,
            error_message=(
                "expires_after must not be provided together with "
                "expires_after[anchor]/expires_after[seconds]."
            ),
            staged_paths=staged_paths,
        )
    if expires_after_raw is not None:
        try:
            parsed_expires_after = field_optional_json_object(
                {"expires_after": (expires_after_raw,)},
                "expires_after",
                invalid_json_message="expires_after must be valid JSON.",
                invalid_object_message="expires_after must be an object.",
            )
        except ValidationError as exception:
            await finalize_cleanup_and_raise_invalid_request(
                request,
                registry=registry,
                task_id=task_id,
                error_message=str(exception),
                staged_paths=staged_paths,
            )
        if parsed_expires_after is None:
            await finalize_cleanup_and_raise_invalid_request(
                request,
                registry=registry,
                task_id=task_id,
                error_message="expires_after must be an object.",
                staged_paths=staged_paths,
            )
        parsed_expires_anchor = parsed_expires_after.get("anchor")
        parsed_expires_seconds = parsed_expires_after.get("seconds")
        expires_anchor = parsed_expires_anchor if isinstance(parsed_expires_anchor, str) else None
        expires_seconds = (
            parsed_expires_seconds
            if isinstance(parsed_expires_seconds, int)
            and not isinstance(parsed_expires_seconds, bool)
            else None
        )
    if expires_anchor is not None or expires_seconds is not None:
        if expires_anchor is None or expires_seconds is None:
            await finalize_cleanup_and_raise_invalid_request(
                request,
                registry=registry,
                task_id=task_id,
                error_message=(
                    "expires_after requires expires_after[anchor] and expires_after[seconds]."
                ),
                staged_paths=staged_paths,
            )
        if expires_anchor != "created_at":
            await finalize_cleanup_and_raise_invalid_request(
                request,
                registry=registry,
                task_id=task_id,
                error_message="expires_after[anchor] must be 'created_at'.",
                staged_paths=staged_paths,
            )
        if (
            expires_seconds < _FILE_UPLOAD_EXPIRES_MIN_SECONDS
            or expires_seconds > _FILE_UPLOAD_EXPIRES_MAX_SECONDS
        ):
            await finalize_cleanup_and_raise_invalid_request(
                request,
                registry=registry,
                task_id=task_id,
                error_message=(
                    "expires_after[seconds] must be between "
                    f"{_FILE_UPLOAD_EXPIRES_MIN_SECONDS} and "
                    f"{_FILE_UPLOAD_EXPIRES_MAX_SECONDS}."
                ),
                staged_paths=staged_paths,
            )
    return (purpose, expires_anchor, expires_seconds)
