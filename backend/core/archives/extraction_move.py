"""SoAI - Shared extraction temp-dir move logic for archive extractors [backend/core/archives/extraction_move.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager

from core.errors.exceptions import StateError
from core.files.temp_files import create_persistent_staging_directory
from core.filesystem.windows_sharing_conflicts import (
    remove_path_with_sharing_retry,
    rename_with_sharing_retry,
)
from core.logging.trace import get_logger

__all__ = ("move_extracted_items", "staged_archive_extraction")

LOGGER_NAME = "SoAI.core.archives.extraction_move"


def _discard_owned_directory(path: str) -> None:
    try:
        remove_path_with_sharing_retry(path)
    except (OSError, StateError) as exception:
        get_logger(LOGGER_NAME).warning("Extraction cleanup is pending for %s: %s", path, exception)


@contextmanager
def staged_archive_extraction(
    *, destination: str, prefix: str, progress_check: Callable[[], None] | None
) -> Generator[str]:
    os.makedirs(destination, exist_ok=True)
    staging_path = create_persistent_staging_directory(
        prefix=prefix, directory=os.path.dirname(destination) or destination
    )
    try:
        yield staging_path
        if progress_check is not None:
            progress_check()
        move_extracted_items(temp_dir=staging_path, destination=destination)
    finally:
        if os.path.lexists(staging_path):
            _discard_owned_directory(staging_path)


def _restore_replaced_items(replaced_items: list[tuple[str, str]]) -> None:
    for backup_path, dest_path in reversed(replaced_items):
        if os.path.lexists(dest_path):
            remove_path_with_sharing_retry(dest_path)
        rename_with_sharing_retry(backup_path, dest_path)


def _remove_moved_items(moved_items: list[tuple[str, bool]]) -> None:
    for dest_path, had_replacement in reversed(moved_items):
        if had_replacement:
            continue
        if os.path.lexists(dest_path):
            remove_path_with_sharing_retry(dest_path)


def move_extracted_items(*, temp_dir: str, destination: str) -> None:
    destination_parent = os.path.dirname(os.path.abspath(destination)) or destination
    replaced_items: list[tuple[str, str]] = []
    moved_items: list[tuple[str, bool]] = []
    replacement_dir = tempfile.mkdtemp(
        prefix=".soai_extraction_replaced.",
        dir=destination_parent,
    )
    try:
        for item_name in os.listdir(temp_dir):
            source_path = os.path.join(temp_dir, item_name)
            dest_path = os.path.join(destination, item_name)
            had_replacement = os.path.lexists(dest_path)
            if had_replacement:
                backup_path = os.path.join(replacement_dir, item_name)
                rename_with_sharing_retry(dest_path, backup_path)
                replaced_items.append((backup_path, dest_path))
            rename_with_sharing_retry(source_path, dest_path)
            moved_items.append((dest_path, had_replacement))
    except (OSError, StateError) as exception:
        if not _roll_back_extraction(moved_items, replaced_items, replacement_dir):
            exception.add_note("Extraction rollback is incomplete; replaced entries were kept.")
            raise
        _discard_owned_directory(replacement_dir)
        raise
    _discard_owned_directory(replacement_dir)


def _roll_back_extraction(
    moved_items: list[tuple[str, bool]],
    replaced_items: list[tuple[str, str]],
    replacement_dir: str,
) -> bool:
    try:
        _remove_moved_items(moved_items)
        _restore_replaced_items(replaced_items)
    except (OSError, StateError) as rollback_failure:
        get_logger(LOGGER_NAME).error(
            "Extraction rollback is incomplete; replaced entries remain in %s: %s",
            replacement_dir,
            rollback_failure,
        )
        return False
    return True
