"""SoAI - Browser config coercion and persistence path helpers [backend/mcp/tools/browser/config_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.path_policy import ensure_path_within_base_lexical
from core.meta.paths import get_repo_root

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "build_hashed_browser_path",
    "require_browser_path_under_base",
    "resolve_browser_base_dir",
    "resolve_lock_path",
    "slugify_browser_path_token",
)


def resolve_browser_base_dir(
    config: ConfigProtocol,
    key: str,
    *,
    empty_message: str,
) -> str:
    raw_dir = config.get_str(key)
    value = str(raw_dir or "").strip()
    if not value:
        raise ValidationError(empty_message)
    normalized = os.path.normpath(value)
    if os.path.isabs(normalized):
        return normalized
    return os.path.normpath(os.path.join(get_repo_root(), normalized))


def slugify_browser_path_token(value: str, *, label: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        raise ValidationError(f"{label} must be a non-empty string.")
    safe: list[str] = []
    for char in raw:
        if char.isalnum() or char in "._-":
            safe.append(char)
        elif char.isspace():
            safe.append("_")
        else:
            safe.append("_")
    result = "".join(safe).strip("._-")
    if not result:
        raise ValidationError(f"{label} must contain at least one alphanumeric character.")
    if len(result) > 64:
        result = result[:64].rstrip("._-")
    if not result:
        raise ValidationError(f"{label} must contain at least one alphanumeric character.")
    return result


def build_hashed_browser_path(
    *,
    base_dir: str,
    owner_value: str,
    profile: str,
    session_scope: str,
    filename_suffix: str | None,
    version_dir: str | None = None,
) -> str:
    owner = str(owner_value or "").strip()
    if not owner:
        raise ValidationError("Browser path owner value must be a non-empty string.")
    profile_slug = slugify_browser_path_token(profile, label="profile")
    scope_slug = slugify_browser_path_token(session_scope, label="session_scope")
    digest = hashlib.sha256(owner.encode("utf-8", errors="replace")).hexdigest()
    short = digest[:32]
    filename = f"{short}{filename_suffix}" if filename_suffix is not None else short
    if version_dir is not None:
        return os.path.join(base_dir, version_dir, profile_slug, scope_slug, filename)
    return os.path.join(base_dir, profile_slug, scope_slug, filename)


def resolve_lock_path(path: str, *, label: str) -> str:
    value = str(path or "").strip()
    if not value:
        raise ValidationError(f"{label} must be a non-empty string.")
    return f"{os.path.normpath(value)}.lock"


def require_browser_path_under_base(*, base_dir: str, path: str, message: str) -> str:
    resolved = os.path.normpath(str(path or "").strip())
    if not resolved:
        raise ValidationError(message)
    try:
        return ensure_path_within_base_lexical(
            base_dir,
            resolved,
            description="Browser path",
            error_cls=ValidationError,
        )
    except ValidationError as exception:
        raise ValidationError(message) from exception
