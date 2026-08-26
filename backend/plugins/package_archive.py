"""SoAI - Validated plugin package archive access [backend/plugins/package_archive.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import zipfile
from collections.abc import Generator
from contextlib import contextmanager

from core.archives.zip_directory_budget import validate_zip_directory_budget
from core.archives.zip_plan import ValidatedZipPlan, ZipPlanPolicy, build_validated_zip_plan

__all__ = ("open_validated_plugin_package",)


@contextmanager
def open_validated_plugin_package(
    file_handle: io.BufferedIOBase | io.RawIOBase,
) -> Generator[tuple[zipfile.ZipFile, ValidatedZipPlan]]:
    file_handle.seek(0)
    policy = ZipPlanPolicy.plugin_package()
    validate_zip_directory_budget(file_handle, policy.resource_limits)
    with zipfile.ZipFile(file_handle, "r") as zip_file:
        yield zip_file, build_validated_zip_plan(zip_file, policy=policy)
