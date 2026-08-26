"""SoAI - MCP read_audio source and container metadata [backend/mcp/tools/read_audio_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from tinytag import TinyTag, TinyTagException

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.mime_detection import detect_mime_type
from core.filesystem.open_files import open_binary
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_audio_container_metadata", "build_audio_source_metadata")

_MIME_SAMPLE_BYTES = 4096
_LOGGER_NAME = "SoAI.mcp.tools.read_audio_metadata"
_OPERATION_READ_AUDIO_METADATA = "mcp.tools.read_audio_metadata"


def build_audio_source_metadata(file_path: str) -> JSONDict:
    stat_result = os.stat(file_path)
    filename = os.path.basename(file_path)
    _root, extension = os.path.splitext(filename)
    return {
        "path": file_path,
        "filename": filename,
        "extension": extension.lower(),
        "mime_type": _detect_audio_mime_type(file_path),
        "size_bytes": int(stat_result.st_size),
    }


def build_audio_container_metadata(file_path: str) -> JSONDict:
    try:
        tag = TinyTag.get(file_path, image=False)
    except TinyTagException:
        return {
            "metadata_available": False,
            "metadata_error": "Audio metadata is unavailable.",
        }
    except RECOVERABLE_EXCEPTIONS as exception:
        error = StateError(
            f"Audio metadata extraction failed: {type(exception).__name__}: {exception}",
        )
        log_exception(
            get_logger(_LOGGER_NAME),
            error,
            message="Audio metadata extraction failed.",
            operation=_OPERATION_READ_AUDIO_METADATA,
        )
        return {
            "metadata_available": False,
            "metadata_error": "Audio metadata is unavailable.",
        }
    metadata: JSONDict = {"metadata_available": True}
    _add_optional_text(metadata, "title", tag.title)
    _add_optional_text(metadata, "artist", tag.artist)
    _add_optional_text(metadata, "album", tag.album)
    _add_optional_text(metadata, "album_artist", tag.albumartist)
    _add_optional_text(metadata, "genre", tag.genre)
    _add_optional_text(metadata, "year", tag.year)
    _add_optional_text(metadata, "track", tag.track)
    _add_optional_text(metadata, "composer", tag.composer)
    _add_optional_float(metadata, "duration_seconds", tag.duration)
    _add_optional_int(metadata, "bitrate_kbps", tag.bitrate)
    _add_optional_int(metadata, "sample_rate_hz", tag.samplerate)
    _add_optional_int(metadata, "channels", tag.channels)
    return metadata


def _detect_audio_mime_type(file_path: str) -> str:
    with open_binary(file_path, mode="rb") as file_handle:
        sample = file_handle.read(_MIME_SAMPLE_BYTES)
    return (
        detect_mime_type(sample, filename=os.path.basename(file_path)) or "application/octet-stream"
    )


def _add_optional_text(metadata: JSONDict, key: str, value: str | int | None) -> None:
    if value is None:
        return
    rendered = str(value).strip()
    if rendered:
        metadata[key] = rendered


def _add_optional_float(metadata: JSONDict, key: str, value: float | None) -> None:
    if value is None:
        return
    if value > 0.0:
        metadata[key] = float(value)


def _add_optional_int(metadata: JSONDict, key: str, value: float | None) -> None:
    if value is None:
        return
    normalized = int(value)
    if normalized > 0:
        metadata[key] = normalized
