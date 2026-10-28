"""SoAI - Handle-bound Windows publication without replacement [backend/core/files/windows_entry_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import sys
from struct import calcsize, pack

from core.errors.exceptions import StateError
from core.files.windows_directory_operations import (
    open_relative_windows_entry,
    raise_windows_status,
)
from core.files.windows_handle_operations import close_windows_path_resources
from core.filesystem.path_coercion import require_direct_entry_name
from core.system.windows_ctypes import load_windows_library

__all__ = ("rename_windows_directory_without_replacement", "publish_windows_entry_handle")


def publish_windows_entry_handle(handle: int, parent_handle: int, destination: str) -> None:
    require_direct_entry_name(destination)
    destination_bytes = destination.encode("utf-16-le")
    if len(destination_bytes) > 510 or ":" in destination:
        raise StateError("Windows publication name is invalid.")
    rename_header = pack("@IPI", 0, parent_handle, len(destination_bytes))
    information = ctypes.create_string_buffer(rename_header + destination_bytes)
    rename = load_windows_library("ntdll").NtSetInformationFile
    rename.argtypes = (
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int32,
    )
    rename.restype = ctypes.c_int32
    status = ctypes.create_string_buffer(calcsize("@PP"))
    length = len(rename_header) + len(destination_bytes)
    raise_windows_status(
        int(rename(handle, ctypes.byref(status), ctypes.byref(information), length, 10))
    )


def rename_windows_directory_without_replacement(
    parent_handle: int, source: str, destination: str
) -> None:
    handle = open_relative_windows_entry(parent_handle, source, directory=True, delete=True)
    try:
        publish_windows_entry_handle(handle, parent_handle, destination)
    finally:
        close_windows_path_resources(
            [handle], leaf_file_descriptor=-1, primary_exception=sys.exception()
        )
