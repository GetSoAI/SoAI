"""SoAI - File explorer route-scoped dependency resolution [backend/features/api/routes/file_explorer/route_scope_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.files.protocols import (
    FileExplorerBatchProtocol,
    FileExplorerDownloadProtocol,
    FileExplorerListingProtocol,
    FileExplorerTaskLauncherProtocol,
)
from core.files.protocols_explorer import (
    FileExplorerCoreProtocol,
    FileSystemRootScopeProtocol,
)
from core.workspaces.user_workspace_path import resolve_user_record_workspace_access
from features.api.runtime.errors import raise_server_error
from features.api.runtime.user_coercion import current_user_to_json_dict

if TYPE_CHECKING:
    from features.api.runtime.context import ApiContext
    from features.api.runtime.current_user import CurrentUser

__all__ = (
    "FileExplorerBatchScopeContext",
    "FileExplorerCoreScopeContext",
    "FileExplorerDownloadScopeContext",
    "FileExplorerListingScopeContext",
    "FileExplorerTasksScopeContext",
    "require_file_explorer_batch_scoped",
    "require_file_explorer_core_scoped",
    "require_file_explorer_download_scoped",
    "require_file_explorer_listing_scoped",
    "require_file_explorer_tasks_scoped",
)


def _require_workspace_path(current_user: CurrentUser) -> str:
    workspace_value = current_user.get("workspace_path")
    if not isinstance(workspace_value, str) or not workspace_value.strip():
        raise ValidationError("Authenticated user is missing workspace_path.")
    return workspace_value


def _build_root_scope(
    file_explorer_core: FileExplorerCoreProtocol,
    current_user: CurrentUser,
    api_context: ApiContext,
) -> FileSystemRootScopeProtocol:
    workspace_path = _require_workspace_path(current_user)
    resolve_user_record_workspace_access(
        api_context.dependencies.files,
        current_user_to_json_dict(current_user),
    )
    return file_explorer_core.create_workspace_scope(workspace_path)


def _require_file_explorer_core(
    request: Request,
    api_context: ApiContext,
) -> FileExplorerCoreProtocol:
    file_explorer_core = api_context.dependencies.file_explorer_core
    if file_explorer_core is None:
        raise_server_error(request, "File explorer service is not available.")
    return file_explorer_core


@dataclass(frozen=True, slots=True)
class FileExplorerCoreScopeContext:
    root_scope: FileSystemRootScopeProtocol
    file_explorer_core: FileExplorerCoreProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerCoreScopeContext",
            file_explorer_core=self.file_explorer_core,
            root_scope=self.root_scope,
        )


@dataclass(frozen=True, slots=True)
class FileExplorerDownloadScopeContext:
    root_scope: FileSystemRootScopeProtocol
    file_explorer_core: FileExplorerCoreProtocol
    file_explorer_download: FileExplorerDownloadProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerDownloadScopeContext",
            file_explorer_core=self.file_explorer_core,
            file_explorer_download=self.file_explorer_download,
            root_scope=self.root_scope,
        )


@dataclass(frozen=True, slots=True)
class FileExplorerBatchScopeContext:
    root_scope: FileSystemRootScopeProtocol
    file_explorer_batch: FileExplorerBatchProtocol
    file_explorer_core: FileExplorerCoreProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerBatchScopeContext",
            file_explorer_batch=self.file_explorer_batch,
            file_explorer_core=self.file_explorer_core,
            root_scope=self.root_scope,
        )


@dataclass(frozen=True, slots=True)
class FileExplorerTasksScopeContext:
    root_scope: FileSystemRootScopeProtocol
    file_explorer_tasks: FileExplorerTaskLauncherProtocol
    file_explorer_core: FileExplorerCoreProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerTasksScopeContext",
            file_explorer_tasks=self.file_explorer_tasks,
            file_explorer_core=self.file_explorer_core,
            root_scope=self.root_scope,
        )


@dataclass(frozen=True, slots=True)
class FileExplorerListingScopeContext:
    root_scope: FileSystemRootScopeProtocol
    file_explorer_listings: FileExplorerListingProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerListingScopeContext",
            file_explorer_listings=self.file_explorer_listings,
            root_scope=self.root_scope,
        )


def require_file_explorer_core_scoped(
    request: Request,
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
) -> FileExplorerCoreScopeContext:
    file_explorer_core = _require_file_explorer_core(request, api_context)
    return FileExplorerCoreScopeContext(
        root_scope=_build_root_scope(file_explorer_core, current_user, api_context),
        file_explorer_core=file_explorer_core,
    )


def require_file_explorer_download_scoped(
    request: Request,
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
) -> FileExplorerDownloadScopeContext:
    file_explorer_core = _require_file_explorer_core(request, api_context)
    file_explorer_download = api_context.dependencies.file_explorer_download
    if file_explorer_download is None:
        raise_server_error(request, "File explorer download service is not available.")
    return FileExplorerDownloadScopeContext(
        root_scope=_build_root_scope(file_explorer_core, current_user, api_context),
        file_explorer_core=file_explorer_core,
        file_explorer_download=file_explorer_download,
    )


def require_file_explorer_batch_scoped(
    request: Request,
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
) -> FileExplorerBatchScopeContext:
    file_explorer_batch = api_context.dependencies.file_explorer_batch
    file_explorer_core = _require_file_explorer_core(request, api_context)
    if file_explorer_batch is None:
        raise_server_error(request, "File explorer service is not available.")
    return FileExplorerBatchScopeContext(
        root_scope=_build_root_scope(file_explorer_core, current_user, api_context),
        file_explorer_batch=file_explorer_batch,
        file_explorer_core=file_explorer_core,
    )


def require_file_explorer_tasks_scoped(
    request: Request,
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
) -> FileExplorerTasksScopeContext:
    file_explorer_tasks = api_context.dependencies.file_explorer_tasks
    file_explorer_core = _require_file_explorer_core(request, api_context)
    if file_explorer_tasks is None:
        raise_server_error(request, "File explorer service is not available.")
    return FileExplorerTasksScopeContext(
        root_scope=_build_root_scope(file_explorer_core, current_user, api_context),
        file_explorer_tasks=file_explorer_tasks,
        file_explorer_core=file_explorer_core,
    )


def require_file_explorer_listing_scoped(
    request: Request,
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
) -> FileExplorerListingScopeContext:
    file_explorer_core = _require_file_explorer_core(request, api_context)
    file_explorer_listings = api_context.dependencies.file_explorer_listings
    if file_explorer_listings is None:
        raise_server_error(request, "File explorer listing service is not available.")
    return FileExplorerListingScopeContext(
        root_scope=_build_root_scope(file_explorer_core, current_user, api_context),
        file_explorer_listings=file_explorer_listings,
    )
