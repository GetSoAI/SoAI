"""SoAI - Canonical SoAI path recompute helpers [backend/core/workspaces/soai_path_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import ValidationError
from core.files.mime_detection import detect_mime_type
from core.files.workspace_descriptor import (
    canonical_workspace_virtual_path,
    open_workspace_file_descriptor,
    stat_workspace_entry,
)
from core.files.workspace_virtual_paths import (
    conversation_virtual_path_from_real_path,
    conversation_virtual_path_from_user_virtual_path,
)
from core.media_preview.media_preview_classification import (
    classify_mime_type_for_file_preview,
)
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.workspaces.soai_path_fingerprints import build_soai_path_target_fingerprint
from core.workspaces.soai_path_link_codec import DecodedSoaiPathToken

__all__ = (
    "build_soai_path_content_part",
    "build_soai_path_draft_record",
    "conversation_virtual_path_for_user_token",
)

_MIME_SAMPLE_BYTES = 8192


def _title_from_virtual_path(conversation_virtual_path: str) -> str:
    return conversation_virtual_path.rstrip("/").rsplit("/", 1)[-1]


def _workspace_relative_path(conversation_virtual_path: str) -> str:
    return conversation_virtual_path.lstrip("/")


def _detect_file_mime_type(
    workspace_root: str,
    conversation_virtual_path: str,
    fallback_name: str,
) -> tuple[str | None, int, int]:
    opened = open_workspace_file_descriptor(
        workspace_root,
        conversation_virtual_path,
        error_cls=ValidationError,
    )
    try:
        sample = os.read(opened.descriptor, _MIME_SAMPLE_BYTES)
    finally:
        os.close(opened.descriptor)
    return (
        detect_mime_type(sample, filename=fallback_name),
        opened.size_bytes,
        opened.modified_at_ms,
    )


def conversation_virtual_path_for_user_token(
    *,
    user_root: str,
    effective_workspace_root: str,
    token: DecodedSoaiPathToken,
) -> str:
    try:
        return conversation_virtual_path_from_user_virtual_path(
            user_root=user_root,
            effective_workspace_root=effective_workspace_root,
            user_virtual_path=token.virtual_path,
            error_cls=ValidationError,
        )
    except ValidationError as exception:
        _raise_absolute_os_path_token_error(
            user_root=user_root,
            effective_workspace_root=effective_workspace_root,
            token_virtual_path=token.virtual_path,
            cause=exception,
        )
        raise


def _raise_absolute_os_path_token_error(
    *,
    user_root: str,
    effective_workspace_root: str,
    token_virtual_path: str,
    cause: ValidationError,
) -> None:
    if not os.path.isabs(token_virtual_path):
        return
    real_token_path = os.path.realpath(os.path.abspath(token_virtual_path))
    user_root_real = os.path.realpath(os.path.abspath(user_root))
    try:
        relative_to_user_root = os.path.relpath(real_token_path, user_root_real)
    except ValueError:
        return
    if relative_to_user_root in {".", ".."}:
        return
    if relative_to_user_root.startswith(f"..{os.sep}"):
        return
    conversation_virtual_path = conversation_virtual_path_from_real_path(
        effective_workspace_root,
        real_token_path,
        error_cls=ValidationError,
    )
    try:
        stat_workspace_entry(
            effective_workspace_root,
            conversation_virtual_path,
            error_cls=ValidationError,
        )
    except ValidationError:
        return
    raise ValidationError(
        f"SoAI path link uses an OS path. Use File Explorer path '{conversation_virtual_path}' instead.",
    ) from cause


def build_soai_path_content_part(
    *,
    effective_workspace_root: str,
    root_fingerprint: str,
    conversation_virtual_path: str,
    resolved_at_ms: int | None = None,
) -> JSONDict:
    canonical_virtual_path = canonical_workspace_virtual_path(
        effective_workspace_root,
        conversation_virtual_path,
        error_cls=ValidationError,
    )
    entry = stat_workspace_entry(
        effective_workspace_root,
        canonical_virtual_path,
        error_cls=ValidationError,
    )
    title = entry.name or _title_from_virtual_path(canonical_virtual_path)
    if entry.entry_type == "folder":
        mime_type = None
        preview_type = "folder"
        size_bytes = entry.size_bytes
        modified_at_ms = entry.modified_at_ms
    else:
        mime_type, size_bytes, modified_at_ms = _detect_file_mime_type(
            effective_workspace_root,
            canonical_virtual_path,
            title,
        )
        preview_type = classify_mime_type_for_file_preview(mime_type)
    return {
        "type": "soai_path",
        "entry_type": entry.entry_type,
        "source_reference": {
            "type": "conversation_virtual_path",
            "value": canonical_virtual_path,
        },
        "tool_reference": {
            "type": "workspace_relative_path",
            "value": _workspace_relative_path(canonical_virtual_path),
        },
        "workspace_scope": {
            "type": "conversation_effective_workspace",
            "root_fingerprint": root_fingerprint,
        },
        "target_fingerprint": build_soai_path_target_fingerprint(
            effective_workspace_root=effective_workspace_root,
            conversation_virtual_path=canonical_virtual_path,
            entry_type=entry.entry_type,
        ),
        "title": title,
        "preview_type": preview_type,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "modified_at_ms": modified_at_ms,
        "resolved_at_ms": int(epoch_ms() if resolved_at_ms is None else resolved_at_ms),
    }


def build_soai_path_draft_record(
    *,
    user_root: str,
    effective_workspace_root: str,
    root_fingerprint: str,
    token: DecodedSoaiPathToken,
) -> JSONDict:
    conversation_virtual_path = conversation_virtual_path_for_user_token(
        user_root=user_root,
        effective_workspace_root=effective_workspace_root,
        token=token,
    )
    return {
        "token": token.token,
        "occurrence_index": token.occurrence_index,
        "display_label": token.label,
        "content_part": build_soai_path_content_part(
            effective_workspace_root=effective_workspace_root,
            root_fingerprint=root_fingerprint,
            conversation_virtual_path=conversation_virtual_path,
        ),
    }
