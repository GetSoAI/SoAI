"""SoAI - Task-scoped software update preparation progress [backend/app/updater/software_update/preparation_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal

from core.bootstrap.install_filesystem import unlink_if_exists
from core.errors.exceptions import StateError, ValidationError
from core.filesystem.atomic_writes import atomic_write_json_content
from core.filesystem.open_files import read_regular_file_no_symlink
from core.meta.paths import join_data_abs
from core.serialization.json_parsing import parse_json_dict
from core.tasks.identifiers import validate_optional_task_id
from core.timing.epoch import epoch_ms
from core.validation.integers import is_non_negative_strict_int, is_positive_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

    type PreparationPhase = Literal[
        "preparing", "fetching", "verifying", "downloading", "staging", "handoff"
    ]

__all__ = (
    "clear_preparation_progress",
    "read_preparation_progress",
    "report_download_progress",
    "write_preparation_progress",
)

PHASES = frozenset(("preparing", "fetching", "verifying", "downloading", "staging", "handoff"))
MAX_PROGRESS_BYTES = 2048


def _progress_path(base_path: str, task_id: str) -> str:
    canonical = validate_optional_task_id(task_id, field_name="Update preparation task identity")
    if canonical is None or canonical != task_id:
        raise ValidationError("Update preparation task identity must be canonical.")
    return join_data_abs(base_path, "state", f"software-update-{canonical}.progress.json")


def write_preparation_progress(
    base_path: str,
    task_id: str,
    phase: PreparationPhase,
    *,
    downloaded_bytes: int | None = None,
    total_bytes: int | None = None,
) -> None:
    if phase not in PHASES:
        raise ValidationError("Update preparation phase is invalid.")
    if downloaded_bytes is not None and (
        downloaded_bytes < 0
        or total_bytes is None
        or total_bytes <= 0
        or downloaded_bytes > total_bytes
    ):
        raise ValidationError("Update download progress is invalid.")
    if downloaded_bytes is None and total_bytes is not None:
        raise ValidationError("Update download total requires downloaded bytes.")
    atomic_write_json_content(
        _progress_path(base_path, task_id),
        {
            "task_id": task_id,
            "phase": phase,
            "downloaded_bytes": downloaded_bytes,
            "total_bytes": total_bytes,
            "updated_at_ms": epoch_ms(),
        },
    )


def report_download_progress(
    base_path: str,
    task_id: str,
    enabled: bool,
    downloaded_bytes: int,
    total_bytes: int,
) -> None:
    if enabled:
        write_preparation_progress(
            base_path,
            task_id,
            "downloading",
            downloaded_bytes=downloaded_bytes,
            total_bytes=total_bytes,
        )


def read_preparation_progress(base_path: str, task_id: str) -> JSONDict | None:
    progress_path = _progress_path(base_path, task_id)
    if not os.path.lexists(progress_path):
        return None
    raw = read_regular_file_no_symlink(progress_path, max_bytes=MAX_PROGRESS_BYTES)
    if len(raw) > MAX_PROGRESS_BYTES:
        raise StateError("Update preparation progress is too large.")
    payload = parse_json_dict(raw, field="Update preparation progress", reject_duplicate_keys=True)
    if frozenset(payload) != frozenset(
        ("task_id", "phase", "downloaded_bytes", "total_bytes", "updated_at_ms")
    ):
        raise StateError("Update preparation progress fields are invalid.")
    phase = payload.get("phase")
    downloaded = payload.get("downloaded_bytes")
    total = payload.get("total_bytes")
    timestamp = payload.get("updated_at_ms")
    if payload.get("task_id") != task_id or not isinstance(phase, str) or phase not in PHASES:
        raise StateError("Update preparation progress identity or phase is invalid.")
    if not isinstance(timestamp, int) or isinstance(timestamp, bool) or timestamp <= 0:
        raise StateError("Update preparation progress timestamp is invalid.")
    if downloaded is not None and (
        not is_non_negative_strict_int(downloaded)
        or not is_positive_strict_int(total)
        or downloaded > total
    ):
        raise StateError("Update preparation download progress is invalid.")
    if downloaded is None and total is not None:
        raise StateError("Update preparation download total is invalid.")
    return payload


def clear_preparation_progress(base_path: str, task_id: str) -> None:
    unlink_if_exists(_progress_path(base_path, task_id))
