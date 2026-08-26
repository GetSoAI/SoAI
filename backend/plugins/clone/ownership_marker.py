"""SoAI - Clone artifact ownership marker V1 records [backend/plugins/clone/ownership_marker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.atomic_writes import atomic_create_text_content_exclusive
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_dict
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.types.json import JSONDict, JSONValue

__all__ = (
    "DIRECTORY_IDENTITY",
    "OwnershipEntry",
    "OwnershipMarker",
    "artifact_ownership_marker_path",
    "ownership_marker_staging_path",
    "read_ownership_marker",
    "require_ownership_marker",
    "replace_ownership_marker",
    "write_ownership_marker",
)

DIRECTORY_IDENTITY = ".soai-clone-identity"

_MARKER_KEYS = frozenset(
    (
        "artifact_type",
        "device",
        "entries",
        "inode",
        "owner",
        "sha256_hex",
        "size_bytes",
        "state",
        "version",
    )
)
_ENTRY_KEYS = frozenset(
    ("device", "entry_type", "inode", "relative_path", "sha256_hex", "size_bytes")
)


@dataclass(frozen=True, slots=True)
class OwnershipEntry:
    relative_path: str
    entry_type: str
    device: int
    inode: int
    size_bytes: int | None
    sha256_hex: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class OwnershipMarker:
    owner: str
    artifact_type: str
    state: str
    device: int
    inode: int
    size_bytes: int | None
    sha256_hex: str | None
    entries: tuple[OwnershipEntry, ...] = ()


def _encode_marker(marker: OwnershipMarker) -> str:
    payload: JSONDict = {
        "artifact_type": marker.artifact_type,
        "device": marker.device,
        "entries": [
            {
                "device": entry.device,
                "entry_type": entry.entry_type,
                "inode": entry.inode,
                "relative_path": entry.relative_path,
                "sha256_hex": entry.sha256_hex,
                "size_bytes": entry.size_bytes,
            }
            for entry in marker.entries
        ],
        "inode": marker.inode,
        "owner": marker.owner,
        "sha256_hex": marker.sha256_hex,
        "size_bytes": marker.size_bytes,
        "state": marker.state,
        "version": 1,
    }
    return serialize_json_compact_stable(payload)


def write_ownership_marker(path: str, marker: OwnershipMarker) -> None:
    atomic_create_text_content_exclusive(
        path,
        _encode_marker(marker),
        encoding="ascii",
        ensure_parent=False,
        file_mode=0o600,
    )
    fsync_directory(os.path.dirname(path), strict=True)


def artifact_ownership_marker_path(final_path: str) -> str:
    return f"{final_path}.soai-clone-owner"


def ownership_marker_staging_path(path: str, owner: str) -> str:
    return f"{path}.next-{owner}"


def replace_ownership_marker(path: str, marker: OwnershipMarker) -> None:
    staging_path = ownership_marker_staging_path(path, marker.owner)
    atomic_create_text_content_exclusive(
        staging_path,
        _encode_marker(marker),
        encoding="ascii",
        ensure_parent=False,
        file_mode=0o600,
    )
    try:
        os.replace(staging_path, path)
        fsync_directory(os.path.dirname(path), strict=True)
    finally:
        if os.path.lexists(staging_path):
            os.unlink(staging_path)
            fsync_directory(os.path.dirname(path), strict=True)


def _require_int(value: JSONValue, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StateError(f"Clone ownership marker {field_name} is invalid.")
    return value


def _require_optional_size(value: JSONValue, field_name: str) -> int | None:
    if value is None:
        return None
    size_bytes = _require_int(value, field_name)
    if size_bytes < 0:
        raise StateError(f"Clone ownership marker {field_name} is invalid.")
    return size_bytes


def _require_optional_sha256(value: JSONValue, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise StateError(f"Clone ownership marker {field_name} is invalid.")
    return require_canonical_sha256_hexdigest(
        value,
        label=f"Clone ownership marker {field_name}",
    )


def _require_relative_path(value: JSONValue) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise StateError("Clone ownership marker path is invalid.")
    segments = value.split("/")
    if any(not segment or segment in {".", ".."} for segment in segments):
        raise StateError("Clone ownership marker path is invalid.")
    return value


def _decode_entry(value: JSONValue) -> OwnershipEntry:
    if not isinstance(value, dict) or frozenset(value) != _ENTRY_KEYS:
        raise StateError("Clone ownership marker entry is invalid.")
    entry_type = value["entry_type"]
    if not isinstance(entry_type, str) or entry_type not in {"directory", "file"}:
        raise StateError("Clone ownership marker entry type is invalid.")
    size_bytes = _require_optional_size(value["size_bytes"], "entry size")
    sha256_hex = _require_optional_sha256(value["sha256_hex"], "entry digest")
    if (entry_type == "file") != (size_bytes is not None and sha256_hex is not None):
        raise StateError("Clone ownership marker entry content identity is invalid.")
    return OwnershipEntry(
        relative_path=_require_relative_path(value["relative_path"]),
        entry_type=entry_type,
        device=_require_int(value["device"], "entry device"),
        inode=_require_int(value["inode"], "entry inode"),
        size_bytes=size_bytes,
        sha256_hex=sha256_hex,
    )


def read_ownership_marker(path: str) -> OwnershipMarker:
    try:
        with open_regular_binary_no_symlink(
            path,
            not_found_message="Clone artifact ownership marker is unavailable.",
            symlink_message="Clone artifact ownership marker is unavailable.",
            open_message="Clone artifact ownership marker is unavailable.",
            inspect_message="Clone artifact ownership marker is unavailable.",
            regular_file_message="Clone artifact ownership marker is unavailable.",
        ) as handle:
            encoded = handle.read()
        value = parse_json_dict(
            encoded.decode("ascii", errors="strict"),
            field="clone_ownership_marker",
        )
    except (OSError, UnicodeError, ValidationError) as exception:
        raise StateError("Clone artifact ownership marker is unavailable.") from exception
    if not isinstance(value, dict) or frozenset(value) != _MARKER_KEYS:
        raise StateError("Clone artifact ownership marker is invalid.")
    if value["version"] != 1:
        raise StateError("Clone artifact ownership marker version is invalid.")
    owner = value["owner"]
    artifact_type = value["artifact_type"]
    marker_state = value["state"]
    entries_value = value["entries"]
    if not isinstance(owner, str) or not owner:
        raise StateError("Clone artifact ownership marker owner is invalid.")
    if not isinstance(artifact_type, str) or artifact_type not in {"directory", "file"}:
        raise StateError("Clone artifact ownership marker type is invalid.")
    if not isinstance(marker_state, str) or marker_state not in {"claim", "published"}:
        raise StateError("Clone artifact ownership marker state is invalid.")
    if not isinstance(entries_value, list):
        raise StateError("Clone artifact ownership marker entries are invalid.")
    entries = tuple(_decode_entry(entry) for entry in entries_value)
    if len({entry.relative_path for entry in entries}) != len(entries):
        raise StateError("Clone artifact ownership marker contains duplicate paths.")
    size_bytes = _require_optional_size(value["size_bytes"], "size")
    sha256_hex = _require_optional_sha256(value["sha256_hex"], "digest")
    published_file = artifact_type == "file" and marker_state == "published"
    if published_file != (size_bytes is not None and sha256_hex is not None):
        raise StateError("Clone artifact ownership marker content identity is invalid.")
    if artifact_type == "directory" and (size_bytes is not None or sha256_hex is not None):
        raise StateError("Clone directory ownership marker content identity is invalid.")
    return OwnershipMarker(
        owner=owner,
        artifact_type=artifact_type,
        state=marker_state,
        device=_require_int(value["device"], "device"),
        inode=_require_int(value["inode"], "inode"),
        size_bytes=size_bytes,
        sha256_hex=sha256_hex,
        entries=entries,
    )


def require_ownership_marker(
    path: str,
    task_id: str,
    artifact_type: str,
    *,
    require_published: bool,
) -> OwnershipMarker:
    marker = read_ownership_marker(path)
    if marker.owner != task_id or marker.artifact_type != artifact_type:
        raise StateError("Clone artifact ownership mismatch.")
    if require_published and marker.state != "published":
        raise StateError("Clone artifact ownership publication is incomplete.")
    return marker
