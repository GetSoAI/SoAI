"""SoAI - OpenAI file upload flow orchestration [backend/features/api/routes/openai/file_upload_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, status
from starlette.responses import Response

from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import PayloadTooLargeError, SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_files import FileUploadCommand
from core.files.upload_validation import validate_upload_file_type
from core.filesystem.open_files import open_binary
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from features.api.routes.openai.file_upload_validation import (
    validate_file_upload_fields,
)
from features.api.routes.openai.image_upload_quota_lifecycle import (
    make_upload_dispatch_error_handlers,
)
from features.api.routes.openai.storage_owner import resolve_file_storage_owner
from features.api.routes.openai.streaming_upload_command_flow import (
    execute_openai_multipart_upload_flow,
)
from features.api.routes.openai.streaming_upload_error_handling import (
    extract_single_file,
    finalize_cleanup_and_raise,
    finalize_cleanup_and_raise_invalid_request,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import (
    raise_bad_request,
    raise_payload_too_large,
    raise_server_error,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingMultipartResult,
    )

__all__ = ("execute_openai_file_upload_flow",)

LOGGER_NAME = "SoAI.features.api.file_upload_flow"
OPERATION_FILE_UPLOAD_VALIDATE_TYPE = "features.api.file_upload_flow.validate_type"


async def _read_file_sample(path: str) -> bytes:
    def read_sync() -> bytes:
        with open_binary(path, mode="rb") as handle:
            return handle.read(8192)

    return await asyncio.to_thread(read_sync)


async def execute_openai_file_upload_flow(
    request: Request,
    *,
    api_context: ApiContext,
) -> Response:
    registry = api_context.dependencies.task_registry
    max_upload_bytes = resolve_upload_limit_bytes(
        api_context.dependencies.config,
        UploadLimitType.FILE,
    )

    async def build_payload(
        task_id: str,
        parsed: StreamingMultipartResult,
        staged_paths: list[str],
    ) -> tuple[dict[str, JSONValue], JSONDict]:
        staged_part = extract_single_file(parsed.files, "file")
        purpose, _expires_anchor, _expires_seconds = await validate_file_upload_fields(
            request,
            registry=registry,
            task_id=task_id,
            parsed=parsed,
            staged_paths=staged_paths,
        )
        try:
            file_content_sample = await asyncio.wait_for(
                _read_file_sample(staged_part.temp_path),
                timeout=INTERACTIVE_TIMEOUT_SEC,
            )
        except TimeoutError:
            await finalize_cleanup_and_raise(
                request,
                registry=registry,
                task_id=task_id,
                task_status=TaskStatus.FAILED,
                http_status=status.HTTP_504_GATEWAY_TIMEOUT,
                error_type="timeout_error",
                error_message="File validation timed out.",
                staged_paths=staged_paths,
            )
        try:
            validate_upload_file_type(
                content_type=None,
                file_content_sample=file_content_sample,
                purpose=purpose,
                filename=staged_part.original_filename,
            )
        except ValidationError as exception:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="File upload rejected due to validation error.",
                trace_id=request.state.context.trace_id,
                operation=OPERATION_FILE_UPLOAD_VALIDATE_TYPE,
                level="warning",
            )
            await finalize_cleanup_and_raise_invalid_request(
                request,
                registry=registry,
                task_id=task_id,
                error_message=str(exception),
                staged_paths=staged_paths,
            )
        log_audit_event(
            request,
            "UPLOAD_FILE",
            staged_part.original_filename or "uploaded_file",
            {"purpose": purpose},
        )
        api_key_id, user_id = resolve_file_storage_owner(request)
        return (
            {
                "temp_file_path": staged_part.temp_path,
                "original_filename": staged_part.original_filename,
                "purpose": purpose,
                "content_sha256": staged_part.content_sha256,
                "user_id": user_id,
                "api_key_id": api_key_id,
            },
            {},
        )

    on_recoverable_dispatch_error, on_isolation_dispatch_error = (
        make_upload_dispatch_error_handlers(
            operation="files.upload_file",
            recoverable_message="File upload failed during API handling.",
            isolation_message="Unhandled unexpected error while dispatching OpenAI file upload.",
            coerce_isolation_error=True,
        )
    )

    try:
        return await execute_openai_multipart_upload_flow(
            request,
            api_context=api_context,
            command_type=FileUploadCommand,
            audit_action="UPLOAD_FILE",
            audit_target="file_upload",
            operation="files.upload_file",
            required_fields=frozenset({"purpose"}),
            allowed_fields=frozenset(
                {
                    "purpose",
                    "expires_after",
                    "expires_after[anchor]",
                    "expires_after[seconds]",
                },
            ),
            required_file_fields=frozenset({"file"}),
            allowed_file_fields=frozenset({"file"}),
            max_file_bytes=max_upload_bytes,
            max_total_file_bytes=max_upload_bytes,
            build_payload=build_payload,
            on_recoverable_dispatch_error=on_recoverable_dispatch_error,
            on_isolation_dispatch_error=on_isolation_dispatch_error,
        )
    except PayloadTooLargeError as exception:
        raise_payload_too_large(request, str(exception))
    except ValidationError as exception:
        raise_bad_request(request, str(exception))
    except RECOVERABLE_EXCEPTIONS as exception:
        if not isinstance(exception, HTTPException | SoAIError):
            raise_server_error(
                request,
                "Failed to process uploaded file.",
                error_type="upload_error",
            )
        raise
