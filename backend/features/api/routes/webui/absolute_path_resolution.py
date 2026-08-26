"""SoAI - Single absolute path preview resolution [backend/features/api/routes/webui/absolute_path_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError, SecurityError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.rooted_paths import resolve_rooted_path
from core.media_preview.media_preview_classification import (
    classify_mime_type_for_file_preview,
)
from features.api.routes.webui.absolute_paths_contracts import (
    AbsolutePathsResolveError,
    AbsolutePathsResolveOk,
    build_file_explorer_deeplink,
    build_file_explorer_preview_url,
    build_file_explorer_read_url,
)

if TYPE_CHECKING:
    from features.api.routes.webui.absolute_paths_resolution_state import (
        AbsolutePathsResolutionState,
    )

__all__ = ("resolve_one_absolute_path",)

OPERATION = "webui.absolute_paths.resolve"


async def resolve_one_absolute_path(
    *,
    state: AbsolutePathsResolutionState,
    raw_path: str,
) -> AbsolutePathsResolveOk | AbsolutePathsResolveError:
    path_value = str(raw_path or "").strip()
    if not path_value:
        return _build_error(raw_path=raw_path, code="invalid_path", message="Path is empty.")
    if "\x00" in path_value:
        return _build_error(
            raw_path=raw_path,
            code="invalid_path",
            message="Path contains an invalid character.",
        )
    if not os.path.isabs(path_value):
        return _build_error(
            raw_path=raw_path,
            code="invalid_path",
            message="Path must be an absolute OS path.",
        )
    try:
        resolved = await _resolve_validated_absolute_path(state=state, raw_path=raw_path)
    except SecurityError as exception:
        return _build_security_error(
            state=state,
            raw_path=raw_path,
            path_value=path_value,
            exception=exception,
        )
    except ValidationError as exception:
        return _build_error(raw_path=raw_path, code="invalid_path", message=str(exception))
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            state.logger,
            exception,
            message="Absolute path resolution failed",
            operation=OPERATION,
            level="warning",
        )
        return _build_error(raw_path=raw_path, code="server_error", message="Resolution failed.")
    return resolved


async def _resolve_validated_absolute_path(
    *,
    state: AbsolutePathsResolutionState,
    raw_path: str,
) -> AbsolutePathsResolveOk | AbsolutePathsResolveError:
    path_value = str(raw_path or "").strip()
    resolved = resolve_rooted_path(
        path_value,
        base_path=state.effective_root_real,
        description="Absolute file path",
        error_cls=SecurityError,
    )
    virtual_path = state.user_root_scope.to_virtual_path(resolved)
    canonical_path = state.file_explorer_core.canonicalize_virtual_path(
        state.user_root_scope,
        virtual_path,
    )
    missing_open_url = _build_file_open_url(canonical_path=canonical_path)
    try:
        metadata = await state.file_explorer_core.get_metadata(
            state.user_root_scope,
            canonical_path,
            include_hash=False,
        )
    except NotFoundError:
        return _build_error(
            raw_path=raw_path,
            code="not_found",
            message="File not found.",
            virtual_path=canonical_path,
            open_file_explorer_url=missing_open_url,
        )
    if metadata.is_directory:
        return AbsolutePathsResolveOk(
            path=str(raw_path),
            status="ok",
            type="folder",
            virtual_path=canonical_path,
            mime_type=metadata.mime_type,
            size=int(metadata.size),
            preview_url=None,
            download_url=None,
            open_file_explorer_url=_build_folder_open_url(canonical_path=canonical_path),
        )
    preview_type = classify_mime_type_for_file_preview(metadata.mime_type)
    if preview_type == "text":
        preview_url = build_file_explorer_read_url(canonical_path)
    elif preview_type in {"document", "file"}:
        preview_url = None
    else:
        preview_url = build_file_explorer_preview_url(canonical_path, download=False)
    return AbsolutePathsResolveOk(
        path=str(raw_path),
        status="ok",
        type=preview_type,
        virtual_path=canonical_path,
        mime_type=metadata.mime_type,
        size=int(metadata.size),
        preview_url=preview_url,
        download_url=build_file_explorer_preview_url(canonical_path, download=True),
        open_file_explorer_url=_build_file_open_url(canonical_path=canonical_path),
    )


def _build_file_open_url(*, canonical_path: str) -> str:
    directory_path = os.path.dirname(canonical_path.rstrip("/")) or "/"
    return build_file_explorer_deeplink(
        directory_path=directory_path,
        highlight_path=canonical_path,
        search=os.path.basename(canonical_path),
    )


def _build_folder_open_url(*, canonical_path: str) -> str:
    return build_file_explorer_deeplink(
        directory_path=canonical_path,
        highlight_path=None,
        search=None,
    )


def _build_security_error(
    *,
    state: AbsolutePathsResolutionState,
    raw_path: str,
    path_value: str,
    exception: SecurityError,
) -> AbsolutePathsResolveError:
    user_root_virtual_path: str | None = None
    user_root_open_url: str | None = None
    try:
        user_root_virtual_path = state.user_root_scope.to_virtual_path(
            os.path.realpath(os.path.abspath(path_value)),
        )
        user_root_canonical = state.file_explorer_core.canonicalize_virtual_path(
            state.user_root_scope,
            user_root_virtual_path,
        )
        user_root_open_url = _build_file_open_url(canonical_path=user_root_canonical)
        user_root_virtual_path = user_root_canonical
    except (SecurityError, ValidationError):
        user_root_virtual_path = None
        user_root_open_url = None
    return _build_error(
        raw_path=raw_path,
        code="outside_root",
        message=str(exception),
        virtual_path=user_root_virtual_path,
        open_file_explorer_url=user_root_open_url,
    )


def _build_error(
    *,
    raw_path: str,
    code: str,
    message: str,
    virtual_path: str | None = None,
    open_file_explorer_url: str | None = None,
) -> AbsolutePathsResolveError:
    return AbsolutePathsResolveError(
        path=str(raw_path),
        status="error",
        error_code=code,
        error_message=message,
        virtual_path=virtual_path,
        open_file_explorer_url=open_file_explorer_url,
    )
