"""SoAI - Plugin SDK generic model artifact helpers [backend/plugin_sdk/contracts/model_artifacts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass

from core.plugins.sdk_public_exports import MODEL_ARTIFACT_EXPORTS
from plugin_sdk.contracts.safe_paths import safe_join_under_base

__all__ = MODEL_ARTIFACT_EXPORTS


@dataclass(frozen=True, slots=True)
class RemoteArtifactFile:
    path: str
    size_bytes: int | None
    checksum: str | None


@dataclass(frozen=True, slots=True)
class RemoteArtifact:
    artifact_name: str
    directory_name: str
    primary_path: str
    source_directory: str
    total_size_bytes: int
    checksum: str | None
    files: tuple[RemoteArtifactFile, ...]


@dataclass(frozen=True, slots=True)
class LocalArtifact:
    directory_path: str
    directory_name: str
    primary_path: str
    shard_count: int
    files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PendingArtifact:
    artifact_name: str
    primary_path: str
    source_directory: str
    total_size_bytes: int
    checksum: str | None
    files: tuple[RemoteArtifactFile, ...]


def parse_artifact_shard_filename(
    filename: str,
    *,
    file_suffix: str,
) -> tuple[str, int, int] | None:
    normalized_suffix = _normalize_suffix(file_suffix)
    pattern = rf"(.+?)-(\d{{5}})-of-(\d{{5}}){re.escape(normalized_suffix)}$"
    match = re.match(pattern, filename or "", re.IGNORECASE)
    if match is None:
        return None
    try:
        return match.group(1), int(match.group(2)), int(match.group(3))
    except (TypeError, ValueError):
        return None


def build_artifact_directory_name(name: str, *, file_suffix: str) -> str:
    normalized_suffix = _normalize_suffix(file_suffix)
    candidate = (name or "").strip()
    if not candidate:
        candidate = "model"
    if candidate.lower().endswith(normalized_suffix):
        candidate = candidate[: -len(normalized_suffix)]
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate).strip("._-")
    if not sanitized:
        sanitized = "model"
    return f"{sanitized}{normalized_suffix}"


def build_direct_artifact_directory(
    base_dir: str,
    filename: str,
    source: str,
    *,
    file_suffix: str,
    description: str,
) -> str:
    artifact_base = os.path.splitext(os.path.basename(filename or ""))[0] or "model"
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()[:8]
    directory_name = build_artifact_directory_name(
        f"{artifact_base}--{source_hash}",
        file_suffix=file_suffix,
    )
    relative_path = os.path.join("direct", directory_name)
    return safe_join_under_base(
        base_dir=base_dir,
        relative_path=relative_path,
        description=description,
    )


def collect_artifact_directories(root_dir: str, *, directory_suffix: str) -> list[str]:
    normalized_suffix = _normalize_suffix(directory_suffix)
    if not os.path.isdir(root_dir):
        return []
    directories: list[str] = []
    for current_root, child_dirs, _filenames in os.walk(root_dir):
        if os.path.basename(current_root).lower().endswith(normalized_suffix):
            directories.append(current_root)
            child_dirs[:] = []
    directories.sort()
    return directories


def inspect_artifact_directory(directory_path: str, *, file_suffix: str) -> LocalArtifact:
    normalized_suffix = _normalize_suffix(file_suffix)
    if not os.path.isdir(directory_path):
        raise ValueError(f"Artifact directory does not exist: {directory_path}")
    remote_files: list[RemoteArtifactFile] = []
    path_by_relative: dict[str, str] = {}
    for current_root, _child_dirs, filenames in os.walk(directory_path):
        for filename in sorted(filenames):
            if not filename.lower().endswith(normalized_suffix):
                continue
            full_path = os.path.join(current_root, filename)
            if not os.path.isfile(full_path):
                continue
            relative_path = os.path.relpath(full_path, directory_path).replace(os.sep, "/")
            remote_files.append(
                RemoteArtifactFile(path=relative_path, size_bytes=None, checksum=None),
            )
            path_by_relative[relative_path] = full_path
    grouped = group_remote_artifact_files(remote_files, file_suffix=normalized_suffix)
    if len(grouped) != 1:
        raise ValueError(
            f"Expected exactly one artifact inside {directory_path}, found {len(grouped)}.",
        )
    artifact = grouped[0]
    primary_path = path_by_relative.get(artifact.primary_path)
    if primary_path is None:
        raise ValueError(f"Artifact entrypoint is missing for {directory_path}.")
    file_paths = tuple(
        path_by_relative[file.path] for file in artifact.files if file.path in path_by_relative
    )
    return LocalArtifact(
        directory_path=directory_path,
        directory_name=os.path.basename(directory_path),
        primary_path=primary_path,
        shard_count=len(artifact.files),
        files=file_paths,
    )


def group_remote_artifact_files(
    files: Sequence[RemoteArtifactFile],
    *,
    file_suffix: str,
) -> tuple[RemoteArtifact, ...]:
    normalized_suffix = _normalize_suffix(file_suffix)
    grouped: dict[tuple[str, str, int], list[RemoteArtifactFile]] = {}
    for entry in files:
        path = (entry.path or "").strip()
        if not path.lower().endswith(normalized_suffix):
            continue
        basename = os.path.basename(path)
        shard_info = parse_artifact_shard_filename(basename, file_suffix=normalized_suffix)
        if shard_info is None:
            group_key = (os.path.dirname(path), basename, 0)
        else:
            group_key = (os.path.dirname(path), shard_info[0], shard_info[2])
        grouped_entries = grouped.get(group_key)
        if grouped_entries is None:
            grouped_entries = []
            grouped[group_key] = grouped_entries
        grouped_entries.append(entry)
    pending = _build_pending_artifacts(tuple(grouped.values()), file_suffix=normalized_suffix)
    return _build_remote_artifacts(pending, file_suffix=normalized_suffix)


def _build_pending_artifacts(
    grouped_files: Sequence[list[RemoteArtifactFile]],
    *,
    file_suffix: str,
) -> list[_PendingArtifact]:
    pending: list[_PendingArtifact] = []
    for entries in grouped_files:
        sorted_entries = sorted(entries, key=lambda item: item.path.lower())
        primary = sorted_entries[0]
        basename = os.path.basename(primary.path)
        shard_info = parse_artifact_shard_filename(basename, file_suffix=file_suffix)
        if shard_info is None:
            artifact_name = os.path.splitext(basename)[0]
            checksum = primary.checksum
        else:
            artifact_name = shard_info[0]
            checksum = None
            sorted_entries = sorted(
                sorted_entries,
                key=lambda item: parse_artifact_shard_filename(
                    os.path.basename(item.path) or "",
                    file_suffix=file_suffix,
                )
                or ("", 0, 0),
            )
            primary = sorted_entries[0]
        total_size = sum(
            int(remote_file.size_bytes)
            for remote_file in sorted_entries
            if remote_file.size_bytes is not None and remote_file.size_bytes > 0
        )
        pending.append(
            _PendingArtifact(
                artifact_name=artifact_name,
                primary_path=primary.path,
                source_directory=os.path.dirname(primary.path),
                total_size_bytes=total_size,
                checksum=checksum,
                files=tuple(sorted_entries),
            ),
        )
    pending.sort(key=lambda item: item.primary_path.lower())
    return pending


def _build_remote_artifacts(
    pending: Sequence[_PendingArtifact],
    *,
    file_suffix: str,
) -> tuple[RemoteArtifact, ...]:
    directory_counts: dict[str, int] = {}
    artifacts: list[RemoteArtifact] = []
    for pending_artifact in pending:
        base_name = build_artifact_directory_name(
            pending_artifact.artifact_name,
            file_suffix=file_suffix,
        )
        seen = directory_counts.get(base_name, 0)
        directory_counts[base_name] = seen + 1
        directory_name = base_name if seen == 0 else _indexed_directory_name(base_name, seen + 1)
        artifacts.append(
            RemoteArtifact(
                artifact_name=pending_artifact.artifact_name,
                directory_name=directory_name,
                primary_path=pending_artifact.primary_path,
                source_directory=pending_artifact.source_directory,
                total_size_bytes=pending_artifact.total_size_bytes,
                checksum=pending_artifact.checksum,
                files=pending_artifact.files,
            ),
        )
    return tuple(artifacts)


def _indexed_directory_name(directory_name: str, index: int) -> str:
    stem, extension = os.path.splitext(directory_name)
    return f"{stem}--{index}{extension}"


def _normalize_suffix(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        raise ValueError("file_suffix must not be empty.")
    if normalized.startswith("."):
        return normalized
    return f".{normalized}"
