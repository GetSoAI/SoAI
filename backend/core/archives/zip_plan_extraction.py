"""SoAI - Validated ZIP plan extraction execution [backend/core/archives/zip_plan_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import zipfile
from collections.abc import Callable

from core.archives.constants import CHUNK_READ_SIZE, ensure_parent_exists
from core.archives.zip_plan import ValidatedZipMember, ValidatedZipPlan
from core.filesystem.open_files import open_binary

__all__ = ("extract_validated_zip_members", "extract_validated_zip_plan")


def extract_validated_zip_plan(
    zip_file: zipfile.ZipFile,
    plan: ValidatedZipPlan,
    destination: str,
    *,
    progress_check: Callable[[], None] | None = None,
) -> list[str]:
    return extract_validated_zip_members(
        zip_file,
        plan.members,
        destination,
        progress_check=progress_check,
    )


def extract_validated_zip_members(
    zip_file: zipfile.ZipFile,
    members: tuple[ValidatedZipMember, ...],
    destination: str,
    *,
    progress_check: Callable[[], None] | None = None,
) -> list[str]:
    extracted: list[str] = []
    for member in members:
        if progress_check is not None:
            progress_check()
        target_path = os.path.join(destination, member.destination_path)
        if member.is_directory:
            os.makedirs(target_path, exist_ok=True)
            extracted.append(member.archive_path)
            continue
        ensure_parent_exists(target_path)
        with zip_file.open(member.zip_info) as source_stream:
            with open_binary(target_path, mode="wb") as destination_stream:
                while True:
                    if progress_check is not None:
                        progress_check()
                    chunk = source_stream.read(CHUNK_READ_SIZE)
                    if not chunk:
                        break
                    destination_stream.write(chunk)
        extracted.append(member.archive_path)
    return extracted
