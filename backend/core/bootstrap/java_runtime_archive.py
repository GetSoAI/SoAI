"""SoAI - Managed Java runtime binary lookup [backend/core/bootstrap/java_runtime_archive.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import StateError

__all__ = ("find_java_binary",)


def find_java_binary(extracted_root: str) -> str:
    candidates: list[str] = []
    for dirpath, _, filenames in os.walk(extracted_root):
        base = os.path.basename(dirpath).lower()
        if base != "bin":
            continue
        for filename in filenames:
            lowered = filename.lower()
            if lowered in ("java", "java.exe"):
                candidates.append(os.path.join(dirpath, filename))
    if not candidates:
        raise StateError("Managed Java runtime install is missing a java binary.")
    candidates_sorted = sorted(
        candidates,
        key=lambda path: len(os.path.normpath(path).split(os.sep)),
    )
    java_bin = os.path.abspath(candidates_sorted[0])
    if not os.path.isfile(java_bin):
        raise StateError("Managed Java runtime java binary path is invalid.")
    return java_bin
