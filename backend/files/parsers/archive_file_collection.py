"""SoAI - Archive extracted-file collection helper [backend/files/parsers/archive_file_collection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

__all__ = ("collect_extracted_files",)


def collect_extracted_files(temp_dir: str) -> list[tuple[str, str]]:
    extracted_files: list[tuple[str, str]] = []
    for root_dir, _, files in os.walk(temp_dir):
        for filename in files:
            extracted_path = os.path.join(root_dir, filename)
            relative_path = os.path.relpath(extracted_path, temp_dir)
            extracted_files.append((relative_path, extracted_path))
    extracted_files.sort(key=lambda item: item[0].casefold())
    return extracted_files
