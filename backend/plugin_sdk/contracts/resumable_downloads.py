"""SoAI - Resumable artifact download state [backend/plugin_sdk/contracts/resumable_downloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass

from core.errors.exceptions import ValidationError

__all__ = (
    "open_resumable_download",
    "DownloadResponseRange",
    "resolve_download_response_range",
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


@dataclass(frozen=True, slots=True)
class DownloadResponseRange:
    offset: int
    total_length: int | None


def resolve_download_response_range(
    *,
    status_code: int,
    headers: Mapping[str, str],
    offset: int,
    content_length: int | None,
) -> DownloadResponseRange:
    content_range = headers.get("Content-Range") or headers.get("content-range")
    if status_code == 200 and content_range is None:
        return DownloadResponseRange(offset=0, total_length=content_length)
    if status_code != PARTIAL_CONTENT_STATUS_CODE or offset <= 0 or content_range is None:
        raise ValidationError("The artifact server returned an invalid download response.")
    range_match = re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", content_range)
    if range_match is None:
        raise ValidationError("The artifact server returned an invalid download range.")
    try:
        range_start, range_end, total_length = (int(value) for value in range_match.groups())
    except ValueError as exception:
        raise ValidationError(
            "The artifact server returned an invalid download range."
        ) from exception
    if range_start != offset or range_end < range_start or range_end != total_length - 1:
        raise ValidationError("The artifact server returned an incomplete or mismatched range.")
    if content_length is not None and content_length != total_length - range_start:
        raise ValidationError("The artifact server returned inconsistent download lengths.")
    return DownloadResponseRange(offset=range_start, total_length=total_length)


def open_resumable_download(path: str, *, append: bool) -> io.BufferedWriter:
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_APPEND if append else os.O_TRUNC
    if sys.platform == "win32":
        flags |= os.O_BINARY
    else:
        flags |= os.O_CLOEXEC | os.O_NOFOLLOW
    descriptor = os.open(path, flags, FILE_MODE_OWNER_READ_WRITE)
    return os.fdopen(descriptor, "ab" if append else "wb")
