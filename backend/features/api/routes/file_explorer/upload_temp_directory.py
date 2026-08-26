"""SoAI - File explorer upload temp directory resolution [backend/features/api/routes/file_explorer/upload_temp_directory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.errors.exceptions import ValidationError
from core.files.upload_policy import resolve_temp_directory_path
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_server_error

__all__ = ("resolve_upload_temp_directory",)


def resolve_upload_temp_directory(request: Request, api_context: ApiContext) -> str:
    try:
        return resolve_temp_directory_path(
            api_context.dependencies.config,
            api_context.dependencies.files,
            error_message="SYSTEM.PATHS.TEMP is not configured.",
        )
    except ValidationError as exception:
        raise_server_error(request, exception.message)
