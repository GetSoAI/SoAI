"""SoAI - Anchored Windows directory access, publication and durability [backend/core/files/windows_directory_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from struct import calcsize, pack, unpack_from

from core.errors.exceptions import StateError
from core.files.windows_handle_operations import (
    close_windows_path_resources,
    query_windows_handle_attributes,
)
from core.filesystem.path_coercion import require_direct_entry_name
from core.filesystem.windows_access_control import private_windows_security_descriptor
from core.system.windows_ctypes import last_windows_error, load_kernel32, load_windows_library

__all__ = (
    "raise_windows_status",
    "open_relative_windows_entry",
    "windows_directory_identity",
    "flush_windows_directory",
    "remove_windows_entry",
    "list_windows_directory",
)


def raise_windows_status(status: int) -> None:
    if status >= 0:
        return
    library = load_windows_library("ntdll")
    convert = library.RtlNtStatusToDosError
    convert.argtypes = (ctypes.c_int32,)
    convert.restype = ctypes.c_uint32
    error_number = int(convert(status))
    if error_number in {2, 3}:
        raise FileNotFoundError(
            error_number, "Anchored Windows entry is missing.", None, error_number
        )
    if error_number in {80, 183}:
        raise FileExistsError(
            error_number, "Anchored Windows entry already exists.", None, error_number
        )
    if error_number == 267:
        raise StateError("Anchored Windows directory entry has the wrong type.")
    raise OSError(error_number, "Anchored Windows filesystem operation failed.", None, error_number)


def open_relative_windows_entry(
    parent_handle: int,
    name: str,
    *,
    directory: bool,
    create: bool = False,
    writable: bool = False,
    delete: bool = False,
) -> int:
    require_direct_entry_name(name)
    if len(name.encode("utf-16-le")) > 510 or ":" in name:
        raise StateError("Anchored Windows entry name is invalid.")
    if create:
        with private_windows_security_descriptor() as security:
            return _open_relative_entry(
                parent_handle,
                name,
                directory=directory,
                create=True,
                writable=True,
                delete=delete,
                security=security,
            )
    return _open_relative_entry(
        parent_handle,
        name,
        directory=directory,
        create=False,
        writable=writable,
        delete=delete,
        security=None,
    )


def _open_relative_entry(
    parent_handle: int,
    name: str,
    *,
    directory: bool,
    create: bool,
    writable: bool,
    delete: bool,
    security: ctypes.c_void_p | None,
) -> int:
    name_buffer = ctypes.create_string_buffer(name.encode("utf-16-le") + b"\0\0")
    name_bytes = len(name.encode("utf-16-le"))
    unicode_name = ctypes.create_string_buffer(
        pack("@HHP", name_bytes, name_bytes + 2, ctypes.addressof(name_buffer))
    )
    attributes = ctypes.create_string_buffer(
        pack(
            "@IPPIPP",
            calcsize("@IPPIPP"),
            parent_handle,
            ctypes.addressof(unicode_name),
            0x40,
            security.value if security is not None else 0,
            0,
        )
    )
    status = ctypes.create_string_buffer(calcsize("@PP"))
    handle = ctypes.c_void_p()
    library = load_windows_library("ntdll")
    create_file = library.NtCreateFile
    create_file.argtypes = (
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    create_file.restype = ctypes.c_int32
    access = 0x00100081 | (0x00000116 if writable else 0) | (0x00010000 if delete else 0)
    options = 0x00200020 | (0x00000001 if directory else 0x00000040) | (2 if writable else 0)
    result = int(
        create_file(
            ctypes.byref(handle),
            access,
            ctypes.byref(attributes),
            ctypes.byref(status),
            None,
            0x80,
            3 if directory else 1,
            2 if create else 1,
            options,
            None,
            0,
        )
    )
    raise_windows_status(result)
    if handle.value is None:
        raise StateError("Windows returned no handle for an accepted filesystem open.")
    accepted = False
    try:
        attributes_value = query_windows_handle_attributes(handle.value)
        if attributes_value & 0x400 or bool(attributes_value & 0x10) != directory:
            raise StateError("Anchored Windows entry is a reparse point or has the wrong type.")
        accepted = True
        return handle.value
    finally:
        if not accepted:
            close_windows_path_resources(
                [handle.value], leaf_file_descriptor=-1, primary_exception=sys.exception()
            )


def windows_directory_identity(handle: int) -> tuple[int, int]:
    library = load_kernel32()
    query = library.GetFileInformationByHandleEx
    query.argtypes = (ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32)
    query.restype = ctypes.c_int32
    information = ctypes.create_string_buffer(24)
    if not query(handle, 18, ctypes.byref(information), ctypes.sizeof(information)):
        error_number = last_windows_error()
        raise OSError(
            error_number, "Windows directory identity could not be read.", None, error_number
        )
    return int.from_bytes(information.raw[:8], "little"), int.from_bytes(
        information.raw[8:24], "little"
    )


def flush_windows_directory(handle: int) -> None:
    library = load_windows_library("ntdll")
    flush = library.NtFlushBuffersFile
    flush.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
    flush.restype = ctypes.c_int32
    status = ctypes.create_string_buffer(calcsize("@PP"))
    raise_windows_status(int(flush(handle, ctypes.byref(status))))


def remove_windows_entry(
    parent_handle: int, name: str, *, directory: bool, opener: Callable[[], int] | None = None
) -> None:
    handle = (
        opener()
        if opener is not None
        else open_relative_windows_entry(parent_handle, name, directory=directory, delete=True)
    )
    try:
        library = load_windows_library("ntdll")
        remove = library.NtSetInformationFile
        remove.argtypes = (
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_int32,
        )
        remove.restype = ctypes.c_int32
        status = ctypes.create_string_buffer(calcsize("@PP"))
        readonly = bool(query_windows_handle_attributes(handle) & 1)
        disposition = ctypes.c_uint32(0x11) if readonly else ctypes.c_ubyte(1)
        raise_windows_status(
            int(
                remove(
                    handle,
                    ctypes.byref(status),
                    ctypes.byref(disposition),
                    ctypes.sizeof(disposition),
                    64 if readonly else 13,
                )
            )
        )
    finally:
        close_windows_path_resources(
            [handle], leaf_file_descriptor=-1, primary_exception=sys.exception()
        )


def list_windows_directory(handle: int) -> tuple[str, ...]:
    library = load_windows_library("ntdll")
    query = library.NtQueryDirectoryFile
    query.argtypes = (
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int32,
        ctypes.c_ubyte,
        ctypes.c_void_p,
        ctypes.c_ubyte,
    )
    query.restype = ctypes.c_int32
    names: list[str] = []
    restart = True
    for _batch in range(64):
        buffer = ctypes.create_string_buffer(65536)
        status = ctypes.create_string_buffer(calcsize("@PP"))
        result = int(
            query(
                handle,
                None,
                None,
                None,
                ctypes.byref(status),
                buffer,
                len(buffer),
                12,
                0,
                None,
                int(restart),
            )
        )
        restart = False
        if result & 0xFFFFFFFF == 0x80000006:
            return tuple(sorted(names))
        raise_windows_status(result)
        information_size = int.from_bytes(status.raw[calcsize("@P") :], "little")
        if information_size <= 0 or information_size > len(buffer):
            raise StateError("Windows directory query returned an invalid buffer size.")
        offset = 0
        while True:
            header_size = calcsize("<III")
            if offset + header_size > information_size:
                raise StateError("Windows directory query returned a truncated entry.")
            next_offset, _file_index, file_name_length = unpack_from("<III", buffer, offset)
            start = offset + header_size
            end = start + file_name_length
            if end > information_size or file_name_length % 2:
                raise StateError("Windows directory query returned an invalid name length.")
            name = buffer.raw[start:end].decode("utf-16-le")
            if name not in {".", ".."}:
                names.append(require_direct_entry_name(name))
            if len(names) > 4096:
                raise StateError("Workspace directory exceeds the bounded entry inventory.")
            if next_offset == 0:
                break
            if next_offset < header_size + file_name_length:
                raise StateError("Windows directory query returned an overlapping entry.")
            offset += next_offset
    raise StateError("Windows directory query exceeded its bounded batch count.")
