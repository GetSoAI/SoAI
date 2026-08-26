"""SoAI - File explorer MIME helpers [backend/features/file_explorer/mime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import mimetypes
import os
from typing import TYPE_CHECKING

from core.files.content_types import (
    content_type_is_audio,
    content_type_is_document,
    content_type_is_html,
    content_type_is_image,
    content_type_is_javascript,
    content_type_is_text,
    content_type_is_video,
    normalize_content_type,
)
from core.files.extensions.archives import (
    COMPRESSED_EXTENSIONS,
    TAR_EXTENSIONS,
    ZIP_EXTENSIONS,
)
from core.files.extensions.binaries_extensions_storage_and_data import (
    DATA_EXTENSIONS,
    DATABASE_EXTENSIONS,
    MODEL_EXTENSIONS,
)
from core.files.text_extensions import (
    CONFIG_EXTENSIONS,
    DATA_TEXT_EXTENSIONS,
    MARKDOWN_EXTENSIONS,
    SHELL_SCRIPT_EXTENSIONS,
    resolve_text_file_content_type_from_name,
)

if TYPE_CHECKING:
    from core.files.explorer_models import FileEntryTypeId

__all__ = (
    "classify_file_entry_type",
    "detect_mime_type",
    "file_entry_type_sort_rank",
)


def _is_native_preview_content_type(content_type: str) -> bool:
    return (
        content_type_is_audio(content_type)
        or content_type_is_document(content_type)
        or content_type_is_image(content_type)
        or normalize_content_type(content_type) == "image/svg+xml"
        or content_type_is_video(content_type)
        or content_type_is_text(content_type)
    )


def detect_mime_type(name: str, is_directory: bool) -> str:
    if is_directory:
        return "inode/directory"
    guessed, _ = mimetypes.guess_type(name)
    text_content_type = resolve_text_file_content_type_from_name(name)
    if text_content_type is not None:
        if guessed is not None and _is_native_preview_content_type(guessed):
            return guessed
        return text_content_type
    return guessed or "application/octet-stream"


def classify_file_entry_type(
    name: str,
    mime_type: str,
    *,
    is_directory: bool,
) -> FileEntryTypeId:
    if is_directory:
        return "directory"
    normalized_mime_type = normalize_content_type(mime_type)
    _stem, extension_with_dot = os.path.splitext(name.strip().lower())
    extension = extension_with_dot.removeprefix(".")
    if extension == "soaiplugin":
        return "plugin"
    if extension in MODEL_EXTENSIONS:
        return "model"
    if extension in DATABASE_EXTENSIONS:
        return "database"
    if extension in DATA_EXTENSIONS or extension in DATA_TEXT_EXTENSIONS:
        return "data"
    if extension in SHELL_SCRIPT_EXTENSIONS:
        return "shellScript"
    if extension in MARKDOWN_EXTENSIONS:
        return "markdown"
    if extension in CONFIG_EXTENSIONS:
        return "config"
    if normalized_mime_type in {"application/json", "text/json"} or normalized_mime_type.endswith(
        "+json",
    ):
        return "json"
    if normalized_mime_type == "application/pdf":
        return "pdf"
    if _is_spreadsheet_content_type(normalized_mime_type):
        return "spreadsheet"
    if _is_presentation_content_type(normalized_mime_type):
        return "presentation"
    if content_type_is_document(mime_type):
        return "document"
    if extension in TAR_EXTENSIONS | ZIP_EXTENSIONS | COMPRESSED_EXTENSIONS:
        return "archive"
    if _is_archive_content_type(normalized_mime_type):
        return "archive"
    if content_type_is_audio(mime_type):
        return "audio"
    if normalized_mime_type == "image/jpeg":
        return "jpegImage"
    if normalized_mime_type == "image/png":
        return "pngImage"
    if content_type_is_image(mime_type) or normalized_mime_type == "image/svg+xml":
        return "image"
    if _is_code_content_type(normalized_mime_type):
        return "code"
    if content_type_is_text(mime_type):
        return "text"
    if content_type_is_video(mime_type):
        return "video"
    if normalized_mime_type == "application/octet-stream":
        return "unknownFile"
    return "binary"


def _is_archive_content_type(content_type: str) -> bool:
    return content_type in {
        "application/gzip",
        "application/java-archive",
        "application/vnd.rar",
        "application/x-7z-compressed",
        "application/x-bzip2",
        "application/x-gzip",
        "application/x-rar-compressed",
        "application/x-tar",
        "application/x-xz",
        "application/zip",
        "application/zstd",
    } or content_type.endswith("+zip")


def _is_code_content_type(content_type: str) -> bool:
    return (
        content_type_is_html(content_type)
        or content_type_is_javascript(content_type)
        or content_type.startswith("text/x-")
        or content_type
        in {
            "application/graphql",
            "application/sql",
            "application/wasm",
        }
    )


def _is_presentation_content_type(content_type: str) -> bool:
    return "presentation" in content_type or "powerpoint" in content_type


def _is_spreadsheet_content_type(content_type: str) -> bool:
    return "spreadsheet" in content_type or content_type in {
        "application/vnd.ms-excel",
        "text/csv",
        "text/tab-separated-values",
    }


def file_entry_type_sort_rank(type_id: FileEntryTypeId) -> int:
    match type_id:
        case "directory":
            return 10
        case "shellScript":
            return 20
        case "code":
            return 30
        case "markdown":
            return 40
        case "json":
            return 100
        case "config":
            return 110
        case "text":
            return 120
        case "data":
            return 125
        case "jpegImage":
            return 130
        case "pngImage":
            return 140
        case "image":
            return 150
        case "pdf":
            return 160
        case "document":
            return 170
        case "spreadsheet":
            return 180
        case "presentation":
            return 190
        case "archive":
            return 200
        case "audio":
            return 210
        case "video":
            return 220
        case "database":
            return 230
        case "model":
            return 240
        case "plugin":
            return 250
        case "binary":
            return 260
        case "unknownFile":
            return 270
