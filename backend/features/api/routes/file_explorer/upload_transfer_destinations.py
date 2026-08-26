"""SoAI - File explorer upload destination resolution and validation [backend/features/api/routes/file_explorer/upload_transfer_destinations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import NotFoundError, SecurityError, ValidationError
from features.api.runtime.errors import raise_not_found
from features.api.runtime.task_api_errors import raise_invalid_request_error_with_task
from features.file_explorer.path_resolution import (
    resolve_single_upload_virtual_destination,
)
from features.file_explorer.path_validation import normalize_upload_filename

if TYPE_CHECKING:
    from fastapi import Request

    from core.files.protocols_explorer import (
        FileExplorerCoreProtocol,
        FileSystemRootScopeProtocol,
    )

__all__ = (
    "normalize_upload_filename_value",
    "resolve_single_destination",
)


def normalize_upload_filename_value(request: Request, *, task_id: str, filename: str | None) -> str:
    try:
        return normalize_upload_filename(filename)
    except ValidationError as exception:
        raise_invalid_request_error_with_task(
            request,
            message=exception.message,
            task_id=task_id,
        )


def resolve_single_destination(
    request: Request,
    *,
    task_id: str,
    root_scope: FileSystemRootScopeProtocol,
    file_explorer_core: FileExplorerCoreProtocol,
    base_path: str,
    safe_filename: str,
) -> tuple[str, str]:
    virtual_destination = resolve_single_upload_virtual_destination(
        root_scope,
        file_explorer_core,
        base_path=base_path,
        safe_filename=safe_filename,
    )
    try:
        real_destination = file_explorer_core.get_upload_destination(
            root_scope,
            virtual_destination,
        )
    except SecurityError as exception:
        raise_invalid_request_error_with_task(
            request,
            message=exception.message,
            task_id=task_id,
        )
    except NotFoundError as exception:
        raise_not_found(request, exception.message, extra={"task_id": task_id})
    except ValidationError as exception:
        raise_invalid_request_error_with_task(
            request,
            message=exception.message,
            task_id=task_id,
        )
    return virtual_destination, real_destination
