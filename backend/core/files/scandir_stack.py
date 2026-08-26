"""SoAI - Shared os.scandir stack walking helpers [backend/core/files/scandir_stack.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

__all__ = ("pop_next_scandir_entry",)


def pop_next_scandir_entry(
    stack: list[tuple[str, int, list[os.DirEntry[str]]]],
) -> tuple[str, os.DirEntry[str]] | None:
    while stack:
        directory_path, index_in_dir, entries = stack[-1]
        if index_in_dir >= len(entries):
            stack.pop()
            continue
        entry = entries[index_in_dir]
        stack[-1] = (directory_path, index_in_dir + 1, entries)
        return (directory_path, entry)
    return None
