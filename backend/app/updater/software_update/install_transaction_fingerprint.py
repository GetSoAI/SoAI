"""SoAI - Exact update original fingerprints and descriptor comparison [backend/app/updater/software_update/install_transaction_fingerprint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from enum import Enum

from core.errors.exceptions import StateError
from core.files.staged_transfer import compute_file_sha256
from core.files.windows_reparse_points import is_windows_reparse_point
from core.filesystem.path_coercion import normalize_filesystem_path
from core.serialization.json import serialize_json_compact_stable_strict

__all__ = (
    "MAX_REPORTED_DIFFERENCES",
    "FingerprintComparison",
    "FingerprintDifference",
    "FingerprintDifferenceType",
    "FingerprintSnapshot",
    "capture_fingerprint_snapshot",
    "compare_fingerprint_descriptors",
    "compute_fingerprint_aggregate",
)

MAX_REPORTED_DIFFERENCES = 64
SYMLINK_DESCRIPTOR_PREFIX = "symlink"
FILE_DESCRIPTOR_PREFIX = "file"
DIRECTORY_DESCRIPTOR_PREFIX = "directory"


class FingerprintDifferenceType(Enum):
    MISSING = "missing"
    UNEXPECTED = "unexpected"
    ENTRY_TYPE = "entry_type"
    LINK_TARGET = "link_target"
    MODE = "mode"
    CONTENT_DIGEST = "content_digest"


@dataclass(frozen=True, slots=True)
class FingerprintSnapshot:
    descriptors: dict[str, str]
    aggregate: str


@dataclass(frozen=True, slots=True)
class FingerprintDifference:
    path: str
    difference: FingerprintDifferenceType
    expected: str | None
    actual: str | None


@dataclass(frozen=True, slots=True)
class FingerprintComparison:
    total_differences: int
    differences: tuple[FingerprintDifference, ...]

    @property
    def is_truncated(self) -> bool:
        return self.total_differences > len(self.differences)


def compute_fingerprint_aggregate(descriptors: dict[str, str]) -> str:
    return hashlib.sha256(
        serialize_json_compact_stable_strict(descriptors).encode("utf-8")
    ).hexdigest()


def capture_fingerprint_snapshot(path: str) -> FingerprintSnapshot:
    descriptors: dict[str, str] = {}
    pending = [(normalize_filesystem_path(path), "")]
    while pending:
        entry_path, relative_path = pending.pop()
        metadata = os.lstat(entry_path)
        if is_windows_reparse_point(metadata) and not stat.S_ISLNK(metadata.st_mode):
            raise StateError("Update originals contain an unsupported Windows reparse point.")
        if stat.S_ISLNK(metadata.st_mode):
            descriptors[relative_path] = f"{SYMLINK_DESCRIPTOR_PREFIX}:{os.readlink(entry_path)}"
        elif stat.S_ISREG(metadata.st_mode):
            digest = compute_file_sha256(entry_path).sha256_hex
            descriptors[relative_path] = (
                f"{FILE_DESCRIPTOR_PREFIX}:{stat.S_IMODE(metadata.st_mode)}:{digest}"
            )
        elif stat.S_ISDIR(metadata.st_mode):
            descriptors[relative_path] = (
                f"{DIRECTORY_DESCRIPTOR_PREFIX}:{stat.S_IMODE(metadata.st_mode)}"
            )
            for name in os.listdir(entry_path):
                pending.append((os.path.join(entry_path, name), f"{relative_path}/{name}"))
        else:
            raise StateError("Update originals contain an unsupported filesystem entry.")
    return FingerprintSnapshot(descriptors, compute_fingerprint_aggregate(descriptors))


def _classify_difference(expected: str | None, actual: str | None) -> FingerprintDifferenceType:
    if actual is None:
        return FingerprintDifferenceType.MISSING
    if expected is None:
        return FingerprintDifferenceType.UNEXPECTED
    expected_type, _, expected_detail = expected.partition(":")
    actual_type, _, actual_detail = actual.partition(":")
    if expected_type != actual_type:
        return FingerprintDifferenceType.ENTRY_TYPE
    if expected_type == SYMLINK_DESCRIPTOR_PREFIX:
        return FingerprintDifferenceType.LINK_TARGET
    if expected_type == FILE_DESCRIPTOR_PREFIX:
        expected_digest = expected_detail.partition(":")[2]
        actual_digest = actual_detail.partition(":")[2]
        if expected_digest != actual_digest:
            return FingerprintDifferenceType.CONTENT_DIGEST
    return FingerprintDifferenceType.MODE


def compare_fingerprint_descriptors(
    expected: dict[str, str], actual: dict[str, str]
) -> FingerprintComparison:
    differences: list[FingerprintDifference] = []
    total_differences = 0
    for path in sorted(set(expected).union(actual)):
        expected_descriptor = expected.get(path)
        actual_descriptor = actual.get(path)
        if expected_descriptor == actual_descriptor:
            continue
        total_differences += 1
        if len(differences) < MAX_REPORTED_DIFFERENCES:
            differences.append(
                FingerprintDifference(
                    path,
                    _classify_difference(expected_descriptor, actual_descriptor),
                    expected_descriptor,
                    actual_descriptor,
                )
            )
    return FingerprintComparison(total_differences, tuple(differences))
