"""SoAI - Strict preview reference validation helpers [backend/features/api/runtime/preview_contract_reference_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import NotFoundError, SecurityError, ValidationError
from core.files.path_policy import ensure_path_within_base
from core.network.urls import is_local_url, normalize_http_url

if TYPE_CHECKING:
    from features.api.runtime.preview_contract_scope import ConversationPreviewScope

__all__ = (
    "validate_absolute_path_reference",
    "validate_remote_url_reference",
    "validate_virtual_path_reference",
)


def validate_remote_url_reference(target: str) -> tuple[str, str] | None:
    try:
        normalized_url = normalize_http_url(target)
    except ValidationError:
        return ("invalid_remote_url", f'The remote_url reference "{target}" is invalid.')
    if is_local_url(normalized_url):
        return (
            "invalid_remote_url",
            f'The remote_url reference "{target}" points to a local network address and cannot be previewed.',
        )
    if not normalized_url.lower().startswith("https://"):
        return ("invalid_remote_url", f'The remote_url reference "{target}" must use HTTPS.')
    return None


async def validate_absolute_path_reference(
    scope: ConversationPreviewScope,
    target: str,
) -> tuple[str, str] | None:
    normalized_target = str(target or "").strip()
    if not normalized_target:
        return ("invalid_absolute_path_reference", "The absolute_path reference is empty.")
    if "\x00" in normalized_target:
        return (
            "invalid_absolute_path_reference",
            f'The absolute_path reference "{normalized_target}" contains an invalid character.',
        )
    if not os.path.isabs(normalized_target):
        return (
            "invalid_absolute_path_reference",
            f'The absolute_path reference "{normalized_target}" must be an absolute path.',
        )
    try:
        resolved_path = ensure_path_within_base(
            scope.effective_root_real,
            normalized_target,
            description="Absolute preview path",
            error_cls=SecurityError,
        )
        virtual_path = scope.user_root_scope.to_virtual_path(resolved_path)
        canonical_virtual_path = scope.file_explorer_core.canonicalize_virtual_path(
            scope.user_root_scope,
            virtual_path,
        )
        await scope.file_explorer_core.get_metadata(
            scope.user_root_scope,
            canonical_virtual_path,
            include_hash=False,
        )
    except SecurityError:
        return (
            "invalid_absolute_path_reference",
            f'The absolute_path reference "{normalized_target}" is outside the allowed files root.',
        )
    except ValidationError:
        return (
            "invalid_absolute_path_reference",
            f'The absolute_path reference "{normalized_target}" is invalid.',
        )
    except NotFoundError:
        return (
            "invalid_absolute_path_reference",
            f'The absolute_path reference "{normalized_target}" did not resolve to an existing file or folder.',
        )
    return None


async def validate_virtual_path_reference(
    scope: ConversationPreviewScope,
    target: str,
) -> tuple[str, str] | None:
    normalized_target = str(target or "").strip()
    if not normalized_target:
        return ("invalid_virtual_path_reference", "The virtual_path reference is empty.")
    try:
        canonical_virtual_path = scope.file_explorer_core.canonicalize_virtual_path(
            scope.user_root_scope,
            normalized_target,
        )
        await scope.file_explorer_core.get_metadata(
            scope.user_root_scope,
            canonical_virtual_path,
            include_hash=False,
        )
    except SecurityError:
        return (
            "invalid_virtual_path_reference",
            f'The virtual_path reference "{normalized_target}" is outside the allowed files root.',
        )
    except ValidationError:
        return (
            "invalid_virtual_path_reference",
            f'The virtual_path reference "{normalized_target}" is invalid.',
        )
    except NotFoundError:
        return (
            "invalid_virtual_path_reference",
            f'The virtual_path reference "{normalized_target}" did not resolve to an existing file or folder.',
        )
    return None
