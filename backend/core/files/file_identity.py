"""SoAI - Stable filesystem entry identity [backend/core/files/file_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass, field

from core.errors.exceptions import StateError
from core.platform.os import is_windows

__all__ = ("FileIdentity",)


def _require_windows_birthtime_ns(value: os.stat_result) -> int:
    if sys.platform != "win32":
        raise StateError("Windows file identity was requested on a non-Windows platform.")
    try:
        birthtime_ns = int(value.st_birthtime_ns)
    except (AttributeError, TypeError, ValueError) as exception:
        raise StateError("Windows file identity is missing a valid birth timestamp.") from exception
    if birthtime_ns <= 0:
        raise StateError("Windows file identity has an invalid birth timestamp.")
    return birthtime_ns


@dataclass(frozen=True, slots=True)
class FileIdentity:
    device: int
    inode: int
    mode: int
    size: int
    modified_ns: int
    identity_timestamp_ns: int
    observed_ctime_ns: int = field(compare=False, hash=False)

    @classmethod
    def from_stat(cls, value: os.stat_result) -> FileIdentity:
        identity_timestamp_ns = int(value.st_ctime_ns)
        if is_windows():
            identity_timestamp_ns = _require_windows_birthtime_ns(value)
        return cls(
            device=int(value.st_dev),
            inode=int(value.st_ino),
            mode=int(value.st_mode),
            size=int(value.st_size),
            modified_ns=int(value.st_mtime_ns),
            identity_timestamp_ns=identity_timestamp_ns,
            observed_ctime_ns=int(value.st_ctime_ns),
        )

    def matches_descriptor_snapshot(self, other: FileIdentity) -> bool:
        return self == other and self.observed_ctime_ns == other.observed_ctime_ns

    @property
    def is_directory(self) -> bool:
        return stat.S_ISDIR(self.mode)

    @property
    def is_regular_file(self) -> bool:
        return stat.S_ISREG(self.mode)
