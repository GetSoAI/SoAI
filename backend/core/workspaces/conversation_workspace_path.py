"""SoAI - Conversation workspace path resolution [backend/core/workspaces/conversation_workspace_path.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING

from core.errors.exceptions import SecurityError, ValidationError
from core.files.path_policy import ensure_path_within_base
from core.files.workspace_path import (
    resolve_existing_workspace_directory,
    resolve_workspace_real_path,
)
from core.workspaces.user_workspace_path import normalize_workspace_path_update

if TYPE_CHECKING:
    from core.files.protocols import FilesPathResolverProtocol
    from core.types.json import JSONDict

__all__ = (
    "canonicalize_conversation_workspace_path_override_for_update",
    "fingerprint_conversation_workspace_root",
    "read_conversation_workspace_path_override",
    "resolve_conversation_workspace_path_override_for_update",
    "resolve_conversation_workspace_path_override_with_user_root",
    "resolve_effective_conversation_workspace_path",
)


def fingerprint_conversation_workspace_root(root_path: str) -> str:
    digest = hashlib.sha256(root_path.encode("utf-8", errors="surrogateescape")).hexdigest()
    return f"sha256:{digest}"


def read_conversation_workspace_path_override(model_settings: JSONDict) -> str | None:
    raw_value = model_settings.get("workspace_path")
    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        raise ValidationError("model_settings.workspace_path must be a string when provided.")
    stripped = raw_value.strip()
    return stripped or None


def _normalize_conversation_workspace_override(override_workspace_path: str) -> str:
    stripped_override = normalize_workspace_path_update(override_workspace_path)
    if stripped_override is None:
        raise ValidationError(
            "model_settings.workspace_path must be a non-empty string when provided.",
        )
    return stripped_override


def _resolve_absolute_override_with_user_root(
    *,
    user_root_real: str,
    override_workspace_path: str,
    require_existing_directories: bool,
) -> str:
    effective = os.path.realpath(os.path.abspath(override_workspace_path))
    try:
        scoped = ensure_path_within_base(
            user_root_real,
            effective,
            description="Conversation folder override",
            error_cls=SecurityError,
        )
    except SecurityError as exception:
        raise ValidationError(
            "Conversation folder override is outside the current default files folder and has been revoked.",
            details={"reason": "outside_root"},
        ) from exception
    if require_existing_directories:
        try:
            return resolve_existing_workspace_directory(scoped)
        except ValidationError as exception:
            raise ValidationError(
                "Conversation folder override must be an existing directory.",
                details={"reason": "not_directory"},
            ) from exception
    return scoped


def _resolve_override_with_user_root(
    *,
    user_root_real: str,
    override_workspace_path: str,
    require_existing_directories: bool,
) -> str:
    override_candidate = os.path.abspath(os.path.join(user_root_real, override_workspace_path))
    try:
        effective = ensure_path_within_base(
            user_root_real,
            override_candidate,
            description="Conversation folder override",
            error_cls=SecurityError,
        )
    except SecurityError as exception:
        raise ValidationError(
            "Conversation folder override is outside the current default files folder and has been revoked.",
            details={"reason": "outside_root"},
        ) from exception
    if require_existing_directories:
        try:
            return resolve_existing_workspace_directory(effective)
        except ValidationError as exception:
            raise ValidationError(
                "Conversation folder override must be an existing directory.",
                details={"reason": "not_directory"},
            ) from exception
    return effective


def _is_filesystem_root(path: str) -> bool:
    normalized = os.path.realpath(os.path.abspath(path))
    return os.path.dirname(normalized) == normalized


def resolve_conversation_workspace_path_override_with_user_root(
    *,
    user_root_real: str,
    override_workspace_path: str,
    require_existing_directories: bool,
) -> str:
    normalized_override = _normalize_conversation_workspace_override(override_workspace_path)
    if os.path.isabs(normalized_override):
        return _resolve_absolute_override_with_user_root(
            user_root_real=user_root_real,
            override_workspace_path=normalized_override,
            require_existing_directories=require_existing_directories,
        )
    return _resolve_override_with_user_root(
        user_root_real=user_root_real,
        override_workspace_path=normalized_override,
        require_existing_directories=require_existing_directories,
    )


def canonicalize_conversation_workspace_path_override_for_update(
    *,
    files: FilesPathResolverProtocol,
    user_workspace_path: str,
    override_workspace_path: str,
    require_existing_directories: bool,
) -> str:
    normalized_override = _normalize_conversation_workspace_override(override_workspace_path)
    user_root_real = resolve_workspace_real_path(files, user_workspace_path)
    if require_existing_directories and (not os.path.isdir(user_root_real)):
        raise ValidationError(
            "workspace_path must be an existing directory.",
            details={"reason": "invalid_default_root"},
        )
    if os.path.isabs(normalized_override):
        effective = _resolve_absolute_override_with_user_root(
            user_root_real=user_root_real,
            override_workspace_path=normalized_override,
            require_existing_directories=require_existing_directories,
        )
        if effective == user_root_real:
            return "."
        if _is_filesystem_root(user_root_real):
            return effective
        return os.path.relpath(effective, user_root_real)
    effective = resolve_conversation_workspace_path_override_with_user_root(
        user_root_real=user_root_real,
        override_workspace_path=normalized_override,
        require_existing_directories=require_existing_directories,
    )
    return os.path.relpath(effective, user_root_real)


def resolve_conversation_workspace_path_override_for_update(
    *,
    files: FilesPathResolverProtocol,
    user_workspace_path: str,
    override_workspace_path: str,
    require_existing_directories: bool,
) -> str:
    normalized_override = _normalize_conversation_workspace_override(override_workspace_path)
    user_root_real = resolve_workspace_real_path(files, user_workspace_path)
    if require_existing_directories and (not os.path.isdir(user_root_real)):
        raise ValidationError(
            "workspace_path must be an existing directory.",
            details={"reason": "invalid_default_root"},
        )
    if os.path.isabs(normalized_override):
        return _resolve_absolute_override_with_user_root(
            user_root_real=user_root_real,
            override_workspace_path=normalized_override,
            require_existing_directories=require_existing_directories,
        )
    return _resolve_override_with_user_root(
        user_root_real=user_root_real,
        override_workspace_path=normalized_override,
        require_existing_directories=require_existing_directories,
    )


def resolve_effective_conversation_workspace_path(
    *,
    files: FilesPathResolverProtocol,
    user_workspace_path: str,
    override_workspace_path: str | None,
    require_existing_directories: bool,
) -> str:
    user_root_real = resolve_workspace_real_path(files, user_workspace_path)
    if require_existing_directories and (not os.path.isdir(user_root_real)):
        raise ValidationError(
            "workspace_path must be an existing directory.",
            details={"reason": "invalid_default_root"},
        )
    if override_workspace_path is not None:
        normalized_override = _normalize_conversation_workspace_override(override_workspace_path)
        if os.path.isabs(normalized_override):
            return _resolve_absolute_override_with_user_root(
                user_root_real=user_root_real,
                override_workspace_path=normalized_override,
                require_existing_directories=require_existing_directories,
            )
    else:
        normalized_override = None
    if normalized_override is None:
        return user_root_real
    return _resolve_override_with_user_root(
        user_root_real=user_root_real,
        override_workspace_path=normalized_override,
        require_existing_directories=require_existing_directories,
    )
