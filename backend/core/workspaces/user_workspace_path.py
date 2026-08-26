"""SoAI - WebUI user workspace path values [backend/core/workspaces/user_workspace_path.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.files.workspace_path import (
    create_workspace_directory,
    resolve_workspace_real_path,
    validate_workspace_directory_exists,
)
from core.meta.paths import join_data_relative
from core.users.user_id import require_strict_user_id
from core.users.username import require_canonical_username

if TYPE_CHECKING:
    from core.files.protocols import FilesPathResolverProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "UserWorkspaceUpdate",
    "default_user_workspace_path",
    "materialize_workspace_directory",
    "normalize_workspace_path_update",
    "require_authenticated_user_workspace_path",
    "require_default_workspace_path",
    "require_user_record_username",
    "require_user_record_workspace_path",
    "resolve_user_workspace_access",
    "resolve_user_record_workspace_access",
    "resolve_user_workspace_update",
)


@dataclass(frozen=True, slots=True)
class UserWorkspaceUpdate:
    workspace_path: str
    workspace_real_path: str


def default_user_workspace_path(user_id: int) -> str:
    normalized_user_id = require_strict_user_id(user_id)
    return join_data_relative("user_files", "accounts", str(normalized_user_id))


def require_default_workspace_path(value: str, *, owner_user_id: int | None = None) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 1024:
        raise ValidationError("Default workspace path has an invalid length.")
    default_workspace_prefix = f"{join_data_relative('user_files')}/"
    if not value.startswith(default_workspace_prefix):
        raise ValidationError("Default workspace path has an invalid prefix.")
    if "\x00" in value or "\\" in value or ":" in value:
        raise ValidationError("Default workspace path contains an invalid character.")
    segments = value.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise ValidationError("Default workspace path contains an unsafe segment.")
    if owner_user_id is not None and segments[:3] == ["data", "user_files", "accounts"]:
        expected = default_user_workspace_path(owner_user_id)
        if value != expected:
            raise ValidationError("Default workspace account path does not match its owner.")
    return value


def normalize_workspace_path_update(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("workspace_path must be a string or null.")
    stripped = value.strip()
    if not stripped:
        return None
    if "\x00" in stripped:
        raise ValidationError("workspace_path contains an invalid character.")
    return stripped


def require_user_record_username(user: JSONDict) -> str:
    username_value = user.get("username")
    try:
        canonical_username = (
            require_canonical_username(username_value) if isinstance(username_value, str) else None
        )
    except ValidationError as exception:
        raise StateError("User record is missing a canonical username.") from exception
    if canonical_username is None or username_value != canonical_username:
        raise StateError("User record is missing a canonical username.")
    return canonical_username


def require_user_record_workspace_path(user: JSONDict) -> str:
    workspace_value = user.get("workspace_path")
    if isinstance(workspace_value, str):
        workspace_path = workspace_value.strip()
        if workspace_path:
            return workspace_path
    raise StateError("User record is missing workspace_path.")


def require_authenticated_user_workspace_path(value: JSONValue) -> str:
    if isinstance(value, str):
        workspace_path = value.strip()
        if workspace_path:
            return workspace_path
    raise StateError("Authenticated user is missing workspace_path.")


def materialize_workspace_directory(
    files: FilesPathResolverProtocol,
    workspace_path: str,
) -> str:
    workspace_real_path = resolve_workspace_real_path(files, workspace_path)
    create_workspace_directory(workspace_real_path)
    return workspace_real_path


def resolve_user_workspace_access(
    files: FilesPathResolverProtocol,
    *,
    user_id: int,
    workspace_path: str,
    default_workspace_path: str,
) -> str:
    normalized_user_id = require_strict_user_id(user_id)
    normalized_default = require_default_workspace_path(
        default_workspace_path,
        owner_user_id=normalized_user_id,
    )
    workspace_real_path = resolve_workspace_real_path(files, workspace_path)
    if workspace_path == normalized_default:
        create_workspace_directory(workspace_real_path)
    else:
        validate_workspace_directory_exists(workspace_real_path)
    return workspace_real_path


def resolve_user_record_workspace_access(
    files: FilesPathResolverProtocol,
    user: JSONDict,
) -> str:
    default_workspace_value = user.get("default_workspace_path")
    if not isinstance(default_workspace_value, str):
        raise StateError("User record is missing default_workspace_path.")
    return resolve_user_workspace_access(
        files,
        user_id=require_strict_user_id(user.get("id")),
        workspace_path=require_user_record_workspace_path(user),
        default_workspace_path=default_workspace_value,
    )


def resolve_user_workspace_update(
    files: FilesPathResolverProtocol,
    *,
    default_workspace_path: str,
    requested_value: str | None,
    require_existing_directory: bool,
) -> UserWorkspaceUpdate:
    requested_root = normalize_workspace_path_update(requested_value)
    workspace_path = (
        require_default_workspace_path(default_workspace_path)
        if requested_root is None
        else requested_root
    )
    workspace_real_path = resolve_workspace_real_path(files, workspace_path)
    if requested_root is None:
        create_workspace_directory(workspace_real_path)
    elif require_existing_directory:
        validate_workspace_directory_exists(workspace_real_path)
    return UserWorkspaceUpdate(
        workspace_path=workspace_path,
        workspace_real_path=workspace_real_path,
    )
