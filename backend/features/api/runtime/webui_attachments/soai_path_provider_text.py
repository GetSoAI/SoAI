"""SoAI - Provider-safe SoAI path text rendering [backend/features/api/runtime/webui_attachments/soai_path_provider_text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.integer_requirements import require_config_int_at_least
from core.errors.exceptions import ValidationError
from features.api.runtime.webui_attachments.provider_text_rendering import (
    build_inline_file_content_text,
    sanitize_provider_text_field,
)

if TYPE_CHECKING:
    from core.files.workspace_listing import WorkspaceDirectoryEntry
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.webui_attachments.projection_context import (
        WebuiAttachmentProjectionContext,
    )

__all__ = (
    "build_soai_path_file_content_text",
    "build_soai_path_folder_text",
    "build_soai_path_reference_text",
    "build_soai_path_unavailable_text",
    "require_soai_path_projection_str",
    "resolve_optional_soai_path_title",
)

_FOLDER_LISTING_BEGIN = "[BEGIN UNTRUSTED LINKED FOLDER LISTING]"
_FOLDER_LISTING_END = "[END UNTRUSTED LINKED FOLDER LISTING]"
_FOLDER_ENTRIES_OMITTED = "Additional entries omitted."
_FOLDER_MAX_ENTRIES_KEY = "SERVER.WEBUI.SOAI_LINKS.PROJECTION_FOLDER_MAX_ENTRIES"
_FOLDER_MAX_CHARS_KEY = "SERVER.WEBUI.SOAI_LINKS.PROJECTION_FOLDER_MAX_CHARS"
_FOLDER_MIN_CHARS = 512


def require_soai_path_projection_str(value: JSONValue, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"WebUI SoAI path projection field '{field}' must be a string.")
    return value


def resolve_optional_soai_path_title(part: JSONDict) -> str | None:
    title = part.get("title")
    if not isinstance(title, str):
        return None
    stripped = title.strip()
    return stripped or None


def build_soai_path_reference_text(
    part: JSONDict,
    *,
    note: str | None = None,
    tool_path: str | None = None,
) -> str:
    entry_type = sanitize_provider_text_field(
        require_soai_path_projection_str(part.get("entry_type"), field="entry_type"),
    )
    title = sanitize_provider_text_field(
        require_soai_path_projection_str(part.get("title"), field="title"),
    )
    lines = [f"SoAI internal linked {entry_type or 'target'}: {title or 'linked target'}"]
    if note is not None:
        sanitized_note = sanitize_provider_text_field(note)
        if sanitized_note is not None:
            lines.append(sanitized_note)
    if tool_path is not None:
        sanitized_tool_path = sanitize_provider_text_field(tool_path)
        if sanitized_tool_path is not None:
            lines.append(f"Workspace-relative tool path: {sanitized_tool_path}")
    return "\n".join(lines)


def build_soai_path_unavailable_text(*, title: str | None = None, note: str) -> str:
    label = sanitize_provider_text_field(title) or "linked target"
    sanitized_note = sanitize_provider_text_field(note) or "Live target unavailable."
    return "\n".join((f"SoAI internal {label}: unavailable", sanitized_note))


def build_soai_path_file_content_text(
    part: JSONDict,
    provider_text: str,
    *,
    truncated: bool,
) -> str:
    return build_inline_file_content_text(
        header=build_soai_path_reference_text(part),
        content=provider_text,
        truncated=truncated,
    )


def _folder_entry_line(entry_type: str, name: str, size_bytes: int | None) -> str:
    safe_name = sanitize_provider_text_field(name) or "unnamed"
    if entry_type == "folder":
        return f"- [folder] {safe_name}/"
    return f"- [file] {safe_name} ({size_bytes or 0} bytes)"


def _folder_listing_text_fits(lines: list[str], *, max_chars: int) -> bool:
    return len("\n".join(lines)) <= max_chars


def _append_omission_line(lines: list[str], *, max_chars: int) -> None:
    candidate = [*lines, _FOLDER_ENTRIES_OMITTED]
    if _folder_listing_text_fits(candidate, max_chars=max_chars):
        lines.append(_FOLDER_ENTRIES_OMITTED)


def build_soai_path_folder_text(
    context: WebuiAttachmentProjectionContext,
    part: JSONDict,
    entries: list[WorkspaceDirectoryEntry],
) -> str:
    max_entries = require_config_int_at_least(
        context.dependencies.config.get_int(_FOLDER_MAX_ENTRIES_KEY),
        key=_FOLDER_MAX_ENTRIES_KEY,
        minimum=0,
    )
    max_chars = require_config_int_at_least(
        context.dependencies.config.get_int(_FOLDER_MAX_CHARS_KEY),
        key=_FOLDER_MAX_CHARS_KEY,
        minimum=_FOLDER_MIN_CHARS,
    )
    lines = [
        build_soai_path_reference_text(part),
        _FOLDER_LISTING_BEGIN,
    ]
    truncated = False
    for entry in entries[:max_entries]:
        entry_line = _folder_entry_line(entry.entry_type, entry.name, entry.size_bytes)
        candidate = [*lines, entry_line, _FOLDER_LISTING_END]
        if not _folder_listing_text_fits(candidate, max_chars=max_chars):
            truncated = True
            break
        lines.append(entry_line)
    hidden = len(entries) - min(len(entries), max_entries)
    if hidden > 0:
        hidden_line = f"Additional entries omitted: {hidden}."
        candidate = [*lines, hidden_line, _FOLDER_LISTING_END]
        if _folder_listing_text_fits(candidate, max_chars=max_chars):
            lines.append(hidden_line)
        else:
            truncated = True
    if truncated:
        _append_omission_line(lines, max_chars=max_chars - len(_FOLDER_LISTING_END) - 1)
    lines.append(_FOLDER_LISTING_END)
    return "\n".join(lines)
