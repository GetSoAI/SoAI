"""SoAI - Durable V1 restart purge transaction state [backend/core/restart_purge/transaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import SoAIError, StateError, ValidationError
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.atomic_writes import (
    atomic_create_text_content_exclusive,
    atomic_write_text_content,
)
from core.filesystem.open_files import open_text
from core.serialization.json import serialize_json_pretty_sorted_strict
from core.serialization.json_parsing import parse_json_dict
from core.types.json import is_str_list

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "RestartPurgeManifest",
    "RestartPurgeMarker",
    "create_restart_purge_transaction",
    "complete_committed_restart_purge_cleanup",
    "restart_purge_transaction_required_bytes",
    "load_restart_purge_transaction",
    "serialize_restart_purge_manifest",
    "update_restart_purge_manifest",
    "update_restart_purge_marker",
)


@dataclass(frozen=True, slots=True)
class RestartPurgeMarker:
    state: Literal["preparing", "ready"]


@dataclass(frozen=True, slots=True)
class RestartPurgeManifest:
    state: Literal["pending", "failed", "succeeded"]
    paths_to_delete: tuple[str, ...]
    failed_paths: tuple[str, ...]


def create_restart_purge_transaction(
    *,
    sentinel_path: str,
    manifest_path: str,
    paths_to_delete: tuple[str, ...],
) -> None:
    preparing = RestartPurgeMarker(state="preparing")
    try:
        atomic_create_text_content_exclusive(
            sentinel_path,
            _serialize_marker(preparing),
            fsync=True,
            fsync_parent_directory=True,
        )
    except FileExistsError as exception:
        raise StateError("A restart purge transaction is already active.") from exception
    except (OSError, SoAIError, TypeError, ValueError) as exception:
        _rollback_transaction_paths(
            paths=(sentinel_path,),
            exception=exception,
        )
        raise
    try:
        atomic_create_text_content_exclusive(
            manifest_path,
            serialize_restart_purge_manifest(_pending_manifest(paths_to_delete)),
            fsync=True,
            fsync_parent_directory=True,
        )
    except FileExistsError as exception:
        try:
            os.unlink(sentinel_path)
            fsync_directory(os.path.dirname(sentinel_path))
        except OSError as cleanup_exception:
            raise StateError(
                "Restart purge manifest conflict cleanup failed."
            ) from cleanup_exception
        raise StateError("Restart purge transaction manifest already exists.") from exception
    except (OSError, SoAIError, TypeError, ValueError) as exception:
        _rollback_transaction_paths(
            paths=(manifest_path, sentinel_path),
            exception=exception,
        )
        raise
    try:
        update_restart_purge_marker(sentinel_path, RestartPurgeMarker(state="ready"))
    except (OSError, SoAIError, TypeError, ValueError) as exception:
        _rollback_transaction_paths(
            paths=(manifest_path, sentinel_path),
            exception=exception,
        )
        raise


def restart_purge_transaction_required_bytes(paths_to_delete: tuple[str, ...]) -> int:
    manifest_bytes = len(
        serialize_restart_purge_manifest(_pending_manifest(paths_to_delete)).encode("utf-8")
    )
    preparing_bytes = len(_serialize_marker(RestartPurgeMarker(state="preparing")).encode("utf-8"))
    ready_bytes = len(_serialize_marker(RestartPurgeMarker(state="ready")).encode("utf-8"))
    return manifest_bytes + preparing_bytes + ready_bytes


def load_restart_purge_transaction(
    *,
    sentinel_path: str,
    manifest_path: str,
) -> tuple[RestartPurgeMarker, RestartPurgeManifest]:
    sentinel_exists = os.path.lexists(sentinel_path)
    manifest_exists = os.path.lexists(manifest_path)
    if not sentinel_exists or not manifest_exists:
        missing = "sentinel" if not sentinel_exists else "manifest"
        raise StateError(f"Restart purge transaction {missing} is missing.")
    marker = _parse_marker(_read_json_object(sentinel_path, label="sentinel"))
    manifest = _parse_manifest(_read_json_object(manifest_path, label="manifest"))
    if marker.state != "ready":
        raise StateError("Restart purge transaction was interrupted during preparation.")
    return marker, manifest


def complete_committed_restart_purge_cleanup(
    *,
    sentinel_path: str,
    manifest_path: str,
) -> bool:
    if os.path.lexists(sentinel_path) or not os.path.lexists(manifest_path):
        return False
    manifest = _parse_manifest(_read_json_object(manifest_path, label="manifest"))
    if manifest.state != "succeeded" or manifest.paths_to_delete or manifest.failed_paths:
        raise StateError("Restart purge transaction is missing its commit marker.")
    os.unlink(manifest_path)
    fsync_directory(os.path.dirname(manifest_path))
    return True


def update_restart_purge_marker(path: str, marker: RestartPurgeMarker) -> None:
    atomic_write_text_content(
        path,
        _serialize_marker(marker),
        fsync=True,
        fsync_parent_directory=True,
    )


def update_restart_purge_manifest(path: str, manifest: RestartPurgeManifest) -> None:
    atomic_write_text_content(
        path,
        serialize_restart_purge_manifest(manifest),
        fsync=True,
        fsync_parent_directory=True,
    )


def serialize_restart_purge_manifest(manifest: RestartPurgeManifest) -> str:
    _validate_manifest_state(manifest)
    return serialize_json_pretty_sorted_strict(
        {
            "version": 1,
            "state": manifest.state,
            "paths_to_delete": list(manifest.paths_to_delete),
            "failed_paths": list(manifest.failed_paths),
        }
    )


def _serialize_marker(marker: RestartPurgeMarker) -> str:
    return serialize_json_pretty_sorted_strict({"version": 1, "state": marker.state})


def _pending_manifest(paths_to_delete: tuple[str, ...]) -> RestartPurgeManifest:
    return RestartPurgeManifest(
        state="pending",
        paths_to_delete=paths_to_delete,
        failed_paths=(),
    )


def _read_json_object(path: str, *, label: str) -> JSONDict:
    try:
        with open_text(path, encoding="utf-8", errors="strict") as handle:
            payload = parse_json_dict(
                handle.read(),
                field=f"restart purge transaction {label}",
            )
    except (OSError, UnicodeError, ValidationError) as exception:
        raise StateError(f"Restart purge transaction {label} is invalid.") from exception
    return payload


def _parse_marker(payload: JSONDict) -> RestartPurgeMarker:
    if payload.get("version") != 1 or set(payload) != {"version", "state"}:
        raise StateError("Restart purge transaction sentinel is invalid.")
    state = payload.get("state")
    if state == "preparing":
        return RestartPurgeMarker(state="preparing")
    if state == "ready":
        return RestartPurgeMarker(state="ready")
    raise StateError("Restart purge transaction sentinel is invalid.")


def _parse_manifest(payload: JSONDict) -> RestartPurgeManifest:
    expected_fields = {"version", "state", "paths_to_delete", "failed_paths"}
    if payload.get("version") != 1 or set(payload) != expected_fields:
        raise StateError("Restart purge transaction manifest is invalid.")
    state = payload.get("state")
    paths = payload.get("paths_to_delete")
    failed_paths = payload.get("failed_paths")
    if (
        not is_str_list(paths)
        or not all(paths)
        or not is_str_list(failed_paths)
        or not all(failed_paths)
    ):
        raise StateError("Restart purge transaction manifest is invalid.")
    if state == "pending":
        manifest_state: Literal["pending", "failed", "succeeded"] = "pending"
    elif state == "failed":
        manifest_state = "failed"
    elif state == "succeeded":
        manifest_state = "succeeded"
    else:
        raise StateError("Restart purge transaction manifest is invalid.")
    manifest = RestartPurgeManifest(
        state=manifest_state,
        paths_to_delete=tuple(paths),
        failed_paths=tuple(failed_paths),
    )
    _validate_manifest_state(manifest)
    return manifest


def _validate_manifest_state(manifest: RestartPurgeManifest) -> None:
    remaining_paths = set(manifest.paths_to_delete)
    failed_paths = set(manifest.failed_paths)
    if not failed_paths.issubset(remaining_paths):
        raise StateError("Restart purge transaction manifest is inconsistent.")
    if manifest.state == "succeeded" and (remaining_paths or failed_paths):
        raise StateError("Restart purge transaction manifest is inconsistent.")
    if manifest.state == "failed" and (not remaining_paths or not failed_paths):
        raise StateError("Restart purge transaction manifest is inconsistent.")


def _rollback_transaction_paths(
    *,
    paths: tuple[str, ...],
    exception: BaseException,
) -> None:
    parent_directories: set[str] = set()
    for path in paths:
        try:
            os.unlink(path)
            parent_directories.add(os.path.dirname(path))
        except FileNotFoundError:
            continue
        except OSError as cleanup_exception:
            exception.add_note(f"Restart purge preparation rollback failed: {cleanup_exception}")
    for parent_directory in parent_directories:
        try:
            fsync_directory(parent_directory)
        except OSError as cleanup_exception:
            exception.add_note(f"Restart purge rollback directory sync failed: {cleanup_exception}")
