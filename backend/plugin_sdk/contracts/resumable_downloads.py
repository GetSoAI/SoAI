"""SoAI - Resumable artifact download state [backend/plugin_sdk/contracts/resumable_downloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
from collections.abc import Mapping

from core.errors.exceptions import ValidationError

__all__ = (
    "open_resumable_download",
    "range_response_matches",
    "resume_offset",
)

PARTIAL_CONTENT_STATUS_CODE = 206
FILE_MODE_OWNER_READ_WRITE = 0o600


def resume_offset(path: str, max_bytes: int | None) -> int:
    try:
        stat_result = os.lstat(path)
    except FileNotFoundError:
        return 0
    if not os.path.isfile(path) or os.path.islink(path):
        raise ValidationError("Resumable download state is not a regular file.")
    size = stat_result.st_size
    if max_bytes is not None and size > max_bytes:
        os.remove(path)
        return 0
    return size


def range_response_matches(
    *,
    status_code: int,
    headers: Mapping[str, str],
    offset: int,
) -> bool:
    content_range = headers.get("Content-Range") or headers.get("content-range")
    return (
        status_code == PARTIAL_CONTENT_STATUS_CODE
        and content_range is not None
        and content_range.startswith(f"bytes {offset}-")
    )


def open_resumable_download(path: str, *, append: bool) -> io.BufferedWriter:
    flags = os.O_WRONLY | os.O_CREAT | os.O_CLOEXEC
    flags |= os.O_APPEND if append else os.O_TRUNC
    if os.name != "nt":
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, FILE_MODE_OWNER_READ_WRITE)
    return os.fdopen(descriptor, "ab" if append else "wb")
