"""SoAI - Windows read-only file deletion [backend/core/files/windows_readonly_deletion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import stat
import sys
from collections.abc import Callable

from core.files.managed_storage_errors import FileInUseError

__all__ = ("remove_file_with_readonly_support", "remove_tree_with_readonly_support")


def _require_not_in_use(exception: PermissionError) -> None:
    if sys.platform != "win32":
        return
    try:
        native_code = exception.winerror
    except AttributeError:
        return
    if native_code in (32, 33):
        raise FileInUseError(
            "Windows denied file removal because the file is in use."
        ) from exception


def _retry_readonly_removal[ReturnType](
    function: Callable[[str], ReturnType],
    path: str,
    exception: BaseException,
) -> None:
    if not isinstance(exception, PermissionError):
        raise exception
    _require_not_in_use(exception)
    os.chmod(path, stat.S_IWRITE)
    function(path)


def remove_file_with_readonly_support(path: str) -> None:
    try:
        os.unlink(path)
    except PermissionError as exception:
        if os.name != "nt":
            raise
        _require_not_in_use(exception)
        os.chmod(path, stat.S_IWRITE)
        os.unlink(path)


def remove_tree_with_readonly_support(path: str) -> None:
    if os.name == "nt":
        shutil.rmtree(path, onexc=_retry_readonly_removal)
        return
    shutil.rmtree(path)
