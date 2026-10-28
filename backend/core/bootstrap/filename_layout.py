"""SoAI - Verified source and packaged filename layouts [backend/core/bootstrap/filename_layout.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

from core.errors.exceptions import StateError
from core.filesystem.open_files import read_regular_file_no_symlink
from core.serialization.json_parsing import parse_json_value
from core.validation.integers import is_strict_int

__all__ = (
    "FILENAME_MAPPINGS",
    "FILENAME_DIGESTS_PATH",
    "PackagedFilename",
    "packaged_filename",
    "load_packaged_filenames",
    "verified_filename_bytes",
    "resolve_release_filename",
)

FILENAME_MAPPINGS = (
    ("CHANGE-DATES.md", "CHANGE_DATES.md"),
    ("COMMERCIAL-LICENSE.md", "COMMERCIAL_LICENSE.md"),
    ("COMMERCIAL-LICENSING-AVAILABILITY.md", "COMMERCIAL_LICENSING_AVAILABILITY.md"),
    ("COMMERCIAL-SUPPORT-TERMS.md", "COMMERCIAL_SUPPORT_TERMS.md"),
    ("ORGANIZATION-EVALUATION-TERMS.md", "ORGANIZATION_EVALUATION_TERMS.md"),
    ("install-soai-from-release.bat", "install_soai_from_release.bat"),
    ("install-soai-from-release.command", "install_soai_from_release.command"),
    ("install-soai-from-release.sh", "install_soai_from_release.sh"),
    ("install-soai-linux.sh", "install_soai_linux.sh"),
    ("install-soai-macos.command", "install_soai_macos.command"),
    ("install-soai-windows.ps1", "install_soai_windows.ps1"),
    ("requirements-dev.txt", "requirements_dev.txt"),
    ("uninstall-soai-linux.sh", "uninstall_soai_linux.sh"),
)
FILENAME_DIGESTS_PATH = "backend/core/bootstrap/filename_digests.json"


@dataclass(frozen=True, slots=True)
class PackagedFilename:
    original: str
    canonical: str
    sha256: str
    mode: int


def packaged_filename(relative_path: str) -> str:
    return next(
        (original for original, canonical in FILENAME_MAPPINGS if canonical == relative_path),
        relative_path,
    )


def load_packaged_filenames(root: str) -> tuple[PackagedFilename, ...]:
    path = os.path.join(root, FILENAME_DIGESTS_PATH)
    if not os.path.lexists(path):
        release_info = os.path.join(root, "release-info-v1.json")
        implementation = os.path.join(root, "backend/core/bootstrap/filename_normalization.py")
        if os.path.isfile(implementation) and os.path.lexists(release_info):
            metadata = parse_json_value(
                read_regular_file_no_symlink(release_info, max_bytes=65536),
                field="filename layout artifact identity",
                reject_duplicate_keys=True,
            )
            if isinstance(metadata, dict) and metadata.get("artifact_type") in {
                "backend",
                "complete",
                "windows",
                "appliance-payload",
            }:
                raise StateError(
                    "Packaged filename verification data is missing; preserve recovery evidence."
                )
        return ()
    payload = parse_json_value(
        read_regular_file_no_symlink(path, max_bytes=65536),
        field="packaged filename digests",
        reject_duplicate_keys=True,
    )
    if not isinstance(payload, list) or not payload:
        raise StateError("Packaged filename verification data is invalid.")
    records: list[PackagedFilename] = []
    for record in payload:
        if not isinstance(record, dict) or set(record) != {
            "original",
            "canonical",
            "sha256",
            "mode",
        }:
            raise StateError("Packaged filename verification fields are invalid.")
        original, canonical, digest, mode = (
            record["original"],
            record["canonical"],
            record["sha256"],
            record["mode"],
        )
        if (
            not isinstance(original, str)
            or not isinstance(canonical, str)
            or (original, canonical) not in FILENAME_MAPPINGS
        ):
            raise StateError("Packaged filename mapping is invalid.")
        if (
            not isinstance(digest, str)
            or re.fullmatch("[a-f0-9]{64}", digest) is None
            or not is_strict_int(mode)
            or mode not in (0o644, 0o755)
        ):
            raise StateError("Packaged filename verification entry is invalid.")
        records.append(PackagedFilename(original, canonical, digest, mode))
    if len({record.original for record in records}) != len(records):
        raise StateError("Packaged filename verification entries repeat.")
    return tuple(records)


def verified_filename_bytes(root: str, relative_path: str, digest: str) -> bytes:
    content = read_regular_file_no_symlink(os.path.join(root, relative_path), max_bytes=2097152)
    if hashlib.sha256(content).hexdigest() != digest:
        raise StateError(f"Release-owned filename has unexpected content: {relative_path}")
    return content


def resolve_release_filename(root: str, relative_path: str) -> str:
    for record in load_packaged_filenames(root):
        if relative_path not in (record.original, record.canonical):
            continue
        selected = (
            record.original
            if os.path.lexists(os.path.join(root, record.original))
            else record.canonical
        )
        verified_filename_bytes(root, selected, record.sha256)
        return selected
    return relative_path
