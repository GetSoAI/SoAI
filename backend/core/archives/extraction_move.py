"""SoAI - Shared extraction temp-dir move logic for archive extractors [backend/core/archives/extraction_move.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import tempfile

__all__ = ("move_extracted_items",)


def _remove_path(path: str) -> None:
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
        return
    os.remove(path)


def _restore_replaced_items(replaced_items: list[tuple[str, str]]) -> None:
    for backup_path, dest_path in reversed(replaced_items):
        if os.path.lexists(dest_path):
            _remove_path(dest_path)
        os.rename(backup_path, dest_path)


def _remove_moved_items(moved_items: list[tuple[str, bool]]) -> None:
    for dest_path, had_replacement in reversed(moved_items):
        if had_replacement:
            continue
        if os.path.lexists(dest_path):
            _remove_path(dest_path)


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
                os.rename(dest_path, backup_path)
                replaced_items.append((backup_path, dest_path))
            os.rename(source_path, dest_path)
            moved_items.append((dest_path, had_replacement))
    except OSError:
        _remove_moved_items(moved_items)
        _restore_replaced_items(replaced_items)
        shutil.rmtree(replacement_dir)
        raise
    shutil.rmtree(replacement_dir)
