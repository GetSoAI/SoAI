"""SoAI - Windows read-only file deletion [backend/core/files/windows_readonly_deletion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import stat
from collections.abc import Callable

__all__ = ("remove_file_with_readonly_support", "remove_tree_with_readonly_support")


def _retry_readonly_removal[ReturnType](
    function: Callable[[str], ReturnType],
    path: str,
    exception: BaseException,
) -> None:
    if not isinstance(exception, PermissionError):
        raise exception
    os.chmod(path, stat.S_IWRITE)
    function(path)


def remove_file_with_readonly_support(path: str) -> None:
    try:
        os.unlink(path)
    except PermissionError:
        if os.name != "nt":
            raise
        os.chmod(path, stat.S_IWRITE)
        os.unlink(path)


def remove_tree_with_readonly_support(path: str) -> None:
    if os.name == "nt":
        shutil.rmtree(path, onexc=_retry_readonly_removal)
        return
    shutil.rmtree(path)
