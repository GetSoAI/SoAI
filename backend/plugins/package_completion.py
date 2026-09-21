"""SoAI - Published plugin package completion records [backend/plugins/package_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.files.content_hashing import hash_seekable_binary_stream_content
from core.filesystem.open_files import (
    open_regular_binary_no_symlink,
    read_regular_file_no_symlink,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.validation.record_fields import require_int, require_non_empty_str
from plugins.package_paths import COMPLETION_RECORD_NAME

if TYPE_CHECKING:
    from plugins.package_audit import PluginPackageAudit

__all__ = (
    "PluginPackageCompletionRecord",
    "build_plugin_package_completion_record",
    "plugin_package_cache_matches",
    "read_plugin_package_completion_record",
    "serialize_plugin_package_completion_record",
)

COMPLETION_RECORD_FIELDS = frozenset(
    {
        "archiveHash",
        "contentTreeSha256",
        "expandedBytes",
        "members",
    }
)


@dataclass(frozen=True, slots=True)
class PluginPackageCompletionRecord:
    archive_hash: str
    expanded_bytes: int
    content_tree_sha256: str
    member_count: int

    def to_payload(self) -> dict[str, str | int]:
        return {
            "archiveHash": self.archive_hash,
            "contentTreeSha256": self.content_tree_sha256,
            "expandedBytes": self.expanded_bytes,
            "members": self.member_count,
        }


def _content_tree_sha256(audit: PluginPackageAudit) -> str:
    digest = hashlib.sha256()
    for member in audit.content.member_digests:
        path_bytes = member.destination_path.encode("utf-8")
        digest.update(len(path_bytes).to_bytes(8, byteorder="big"))
        digest.update(path_bytes)
        digest.update(member.file_size.to_bytes(8, byteorder="big"))
        digest.update(bytes.fromhex(member.sha256_hex))
    return digest.hexdigest()


def build_plugin_package_completion_record(
    audit: PluginPackageAudit,
) -> PluginPackageCompletionRecord:
    return PluginPackageCompletionRecord(
        archive_hash=audit.content.archive_hash,
        expanded_bytes=audit.content.expanded_size,
        content_tree_sha256=_content_tree_sha256(audit),
        member_count=len(audit.content.zip_plan.members),
    )


def serialize_plugin_package_completion_record(
    record: PluginPackageCompletionRecord,
) -> str:
    return serialize_json_compact_stable_strict(record.to_payload(), ensure_ascii=True)


def read_plugin_package_completion_record(
    package_root: str,
) -> PluginPackageCompletionRecord | None:
    entrypoint_path = os.path.join(package_root, "__init__.py")
    completion_path = os.path.join(package_root, COMPLETION_RECORD_NAME)
    if os.path.islink(entrypoint_path) or not os.path.isfile(entrypoint_path):
        return None
    if os.path.islink(completion_path) or not os.path.isfile(completion_path):
        return None
    try:
        completion_bytes = read_regular_file_no_symlink(completion_path, max_bytes=4096)
        if len(completion_bytes) > 4096:
            return None
        payload = parse_json_dict(completion_bytes, field="plugin package completion")
        if set(payload) != COMPLETION_RECORD_FIELDS:
            return None
        archive_hash = require_non_empty_str(
            payload.get("archiveHash"),
            label="archiveHash",
            build_error=ValidationError,
        )
        content_tree_sha256 = require_non_empty_str(
            payload.get("contentTreeSha256"),
            label="contentTreeSha256",
            build_error=ValidationError,
        )
        expanded_bytes = require_int(
            payload.get("expandedBytes"),
            label="expandedBytes",
            build_error=ValidationError,
            minimum=0,
        )
        member_count = require_int(
            payload.get("members"),
            label="members",
            build_error=ValidationError,
            minimum=1,
        )
        require_canonical_sha256_hexdigest(
            archive_hash,
            label="Plugin package completion archiveHash",
        )
        require_canonical_sha256_hexdigest(
            content_tree_sha256,
            label="Plugin package completion contentTreeSha256",
        )
    except (OSError, StateError, ValidationError):
        return None
    return PluginPackageCompletionRecord(
        archive_hash=archive_hash,
        expanded_bytes=expanded_bytes,
        content_tree_sha256=content_tree_sha256,
        member_count=member_count,
    )


def _expected_tree_paths(
    audit: PluginPackageAudit,
) -> tuple[set[str], dict[str, tuple[int, str]]]:
    expected_directories: set[str] = set()
    for member in audit.content.zip_plan.members:
        if member.is_directory:
            expected_directories.add(member.destination_path)
        parent_path = os.path.dirname(member.destination_path)
        while parent_path:
            expected_directories.add(parent_path)
            parent_path = os.path.dirname(parent_path)
    expected_files = {
        member.destination_path: (member.file_size, member.sha256_hex)
        for member in audit.content.member_digests
    }
    return expected_directories, expected_files


def _inspect_published_tree(
    package_root: str,
) -> tuple[set[str], dict[str, tuple[int, str]]] | None:
    if os.path.islink(package_root) or not os.path.isdir(package_root):
        return None
    actual_directories: set[str] = set()
    actual_files: dict[str, tuple[int, str]] = {}
    pending_directories = [("", package_root)]
    try:
        while pending_directories:
            relative_root, absolute_root = pending_directories.pop()
            with os.scandir(absolute_root) as entries:
                for entry in entries:
                    relative_path = os.path.join(relative_root, entry.name)
                    if entry.is_symlink():
                        return None
                    if entry.is_dir(follow_symlinks=False):
                        actual_directories.add(relative_path)
                        pending_directories.append((relative_path, entry.path))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        return None
                    if relative_path == COMPLETION_RECORD_NAME:
                        continue
                    with open_regular_binary_no_symlink(
                        entry.path,
                        not_found_message="Cached plugin package member was not found.",
                        symlink_message="Cached plugin package member is a symbolic link.",
                        open_message="Cached plugin package member could not be opened.",
                        inspect_message="Cached plugin package member could not be inspected.",
                        regular_file_message="Cached plugin package member is not a regular file.",
                    ) as file_handle:
                        content_hash = hash_seekable_binary_stream_content(file_handle)
                    actual_files[relative_path] = (
                        content_hash.size_bytes,
                        content_hash.sha256_hex,
                    )
    except (OSError, StateError, ValidationError):
        return None
    return actual_directories, actual_files


def plugin_package_cache_matches(
    package_root: str,
    audit: PluginPackageAudit,
) -> bool:
    completion = read_plugin_package_completion_record(package_root)
    if completion != build_plugin_package_completion_record(audit):
        return False
    actual_tree = _inspect_published_tree(package_root)
    return actual_tree is not None and actual_tree == _expected_tree_paths(audit)
