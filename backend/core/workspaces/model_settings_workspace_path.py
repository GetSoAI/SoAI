"""SoAI - Core model settings workspace path update helpers [backend/core/workspaces/model_settings_workspace_path.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.files.protocols import FilesPathResolverProtocol
from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_json_dict
from core.workspaces.conversation_workspace_path import (
    canonicalize_conversation_workspace_path_override_for_update,
)

__all__ = (
    "apply_model_settings_workspace_path_update",
    "normalize_payload_model_settings_workspace_path",
)


def apply_model_settings_workspace_path_update(
    *,
    files: FilesPathResolverProtocol,
    model_settings: JSONDict,
    raw_workspace_path: JSONValue,
    user_workspace_path: str,
) -> JSONDict:
    next_settings: JSONDict = dict(model_settings)
    if raw_workspace_path is None:
        next_settings.pop("workspace_path", None)
        return next_settings
    if not isinstance(raw_workspace_path, str):
        raise ValidationError("model_settings.workspace_path must be a string or null.")
    override_text = raw_workspace_path.strip()
    if override_text in {"", ".", "/"}:
        next_settings.pop("workspace_path", None)
        return next_settings
    override = canonicalize_conversation_workspace_path_override_for_update(
        files=files,
        user_workspace_path=user_workspace_path,
        override_workspace_path=override_text,
        require_existing_directories=True,
    )
    if override == ".":
        next_settings.pop("workspace_path", None)
    else:
        next_settings["workspace_path"] = override
    return next_settings


def normalize_payload_model_settings_workspace_path(
    *,
    files: FilesPathResolverProtocol,
    payload: JSONDict,
    user_workspace_path: str,
) -> JSONDict:
    model_settings = coerce_json_dict(payload.get("model_settings"))
    if model_settings is None or "workspace_path" not in model_settings:
        return dict(payload)
    next_payload = dict(payload)
    next_payload["model_settings"] = apply_model_settings_workspace_path_update(
        files=files,
        model_settings=model_settings,
        raw_workspace_path=model_settings.get("workspace_path"),
        user_workspace_path=user_workspace_path,
    )
    return next_payload
