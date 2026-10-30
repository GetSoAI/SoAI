"""SoAI - Log export text filenames and rotation selection [backend/app/backup/logs_export_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

from app.backup.internal_protocols import ConfigProviderProtocol
from core.files.content_types import content_type_is_text
from core.files.descriptor_reading import read_descriptor_at
from core.files.extensions.archives import COMPRESSED_EXTENSIONS
from core.files.managed_file_opening import open_managed_file_descriptor
from core.files.managed_storage_traversal import close_file_descriptor_stack
from core.files.mime_detection import detect_mime_type
from core.files.path_policy import is_same_path
from core.logging.configuration_constants import (
    DEFAULT_AUDIT_LOG_FILENAME,
    DEFAULT_LOGS_COMPRESSION_SUFFIX,
    DEFAULT_MAIN_LOG_FILENAME,
)

__all__ = (
    "is_logs_export_file",
    "is_compressed_logs_file",
    "has_logs_export_text_content",
    "resolve_logs_export_file_paths",
)


def is_compressed_logs_file(path: str) -> bool:
    suffix = os.path.splitext(path)[1].lower()
    return suffix.lstrip(".") in COMPRESSED_EXTENSIONS or suffix == DEFAULT_LOGS_COMPRESSION_SUFFIX


def is_logs_export_file(path: str, configured_paths: tuple[str, ...] = ()) -> bool:
    candidates = (path, os.path.splitext(path)[0]) if is_compressed_logs_file(path) else (path,)
    for candidate in candidates:
        name = candidate
        while True:
            if any(is_same_path(name, configured_path) for configured_path in configured_paths):
                return True
            if (
                os.path.basename(name)
                .lower()
                .endswith((".log", ".log.json", ".log.jsonl", ".log.ndjson"))
            ):
                return True
            stem, suffix = os.path.splitext(name)
            rotation = suffix.removeprefix(".")
            if not rotation or not rotation[0].isascii() or not rotation[0].isdigit():
                break
            if not all(character in "0123456789-_+TZtz" for character in rotation):
                break
            name = stem
    return False


def has_logs_export_text_content(root_path: str, path: str) -> bool:
    opened = open_managed_file_descriptor(root_path, path)
    try:
        sample = read_descriptor_at(opened.descriptor, 4096, 0)
        return not sample or content_type_is_text(detect_mime_type(sample))
    finally:
        close_file_descriptor_stack([opened.descriptor], primary_exception=sys.exception())


def resolve_logs_export_file_paths(
    config: ConfigProviderProtocol, source_path: str
) -> tuple[str, ...]:
    paths: list[str] = []
    for key, default_filename in (
        ("OBSERVABILITY.LOGGING.MAIN_LOG", DEFAULT_MAIN_LOG_FILENAME),
        ("OBSERVABILITY.LOGGING.AUDIT.PATH", DEFAULT_AUDIT_LOG_FILENAME),
    ):
        value = config.get(key)
        filename = value.strip() if isinstance(value, str) and value.strip() else default_filename
        paths.append(os.path.abspath(os.path.join(source_path, filename)))
    return tuple(paths)
