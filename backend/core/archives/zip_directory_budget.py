"""SoAI - ZIP central-directory resource preflight [backend/core/archives/zip_directory_budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import struct
import zipfile

from core.archives.resource_limits import ArchivePlanningBudget, ArchiveResourceLimits
from core.errors.exceptions import ValidationError
from core.filesystem.open_files import open_binary

__all__ = ("validate_zip_directory_budget",)

END_RECORD_SIGNATURE = b"PK\x05\x06"
ZIP64_END_RECORD_SIGNATURE = b"PK\x06\x06"
ZIP64_LOCATOR_SIGNATURE = b"PK\x06\x07"
END_RECORD_FORMAT = "<4s4H2LH"
ZIP64_END_RECORD_FORMAT = "<4sQ2H2L4Q"
ZIP64_LOCATOR_FORMAT = "<4sLQL"
CENTRAL_DIRECTORY_FORMAT = "<4s4B4HL2L5H2L"
CENTRAL_DIRECTORY_SIGNATURE = b"PK\x01\x02"
MAX_ZIP_COMMENT_BYTES = 65_535


def validate_zip_directory_budget(
    source: str | io.BufferedIOBase | io.RawIOBase,
    limits: ArchiveResourceLimits,
) -> None:
    if isinstance(source, str):
        with open_binary(source, mode="rb") as file_handle:
            _validate_zip_directory_handle(file_handle, limits)
        return
    _validate_zip_directory_handle(source, limits)


def _validate_zip_directory_handle(
    file_handle: io.BufferedIOBase | io.RawIOBase,
    limits: ArchiveResourceLimits,
) -> None:
    original_position = file_handle.tell()
    try:
        file_handle.seek(0, 2)
        file_size = file_handle.tell()
        search_size = min(
            file_size,
            struct.calcsize(END_RECORD_FORMAT) + MAX_ZIP_COMMENT_BYTES,
        )
        file_handle.seek(file_size - search_size)
        tail = file_handle.read(search_size)
        end_offset, end_record = _find_end_record(tail, file_size - search_size)
        (
            _signature,
            disk_number,
            directory_disk,
            entries_on_disk,
            total_entries,
            directory_size,
            _directory_offset,
            _comment_size,
        ) = end_record
        if disk_number != 0 or directory_disk != 0 or entries_on_disk != total_entries:
            raise zipfile.BadZipFile("Multi-disk ZIP archives are not supported.")
        directory_end_offset = end_offset
        has_zip64_locator = _has_zip64_locator(file_handle, end_offset)
        if has_zip64_locator:
            total_entries, directory_size, directory_end_offset = _read_zip64_directory_values(
                file_handle,
                end_offset,
            )
        elif total_entries == 0xFFFF or directory_size == 0xFFFFFFFF:
            raise zipfile.BadZipFile("ZIP64 locator is missing.")
        _enforce_directory_limits(total_entries, directory_size, limits)
        _validate_central_directory(
            file_handle,
            directory_end_offset=directory_end_offset,
            directory_size=directory_size,
            declared_entries=total_entries,
            limits=limits,
        )
    finally:
        file_handle.seek(original_position)


def _find_end_record(
    tail: bytes,
    tail_offset: int,
) -> tuple[int, tuple[bytes, int, int, int, int, int, int, int]]:
    end_record_size = struct.calcsize(END_RECORD_FORMAT)
    search_end = len(tail)
    while True:
        relative_offset = tail.rfind(END_RECORD_SIGNATURE, 0, search_end)
        if relative_offset < 0:
            raise zipfile.BadZipFile("File is not a ZIP archive.")
        record_end = relative_offset + end_record_size
        if record_end <= len(tail):
            record = struct.unpack(END_RECORD_FORMAT, tail[relative_offset:record_end])
            comment_size = int(record[-1])
            if record_end + comment_size == len(tail):
                return tail_offset + relative_offset, record
        search_end = relative_offset


def _read_zip64_directory_values(
    file_handle: io.BufferedIOBase | io.RawIOBase,
    end_offset: int,
) -> tuple[int, int, int]:
    locator_size = struct.calcsize(ZIP64_LOCATOR_FORMAT)
    zip64_end_record_size = struct.calcsize(ZIP64_END_RECORD_FORMAT)
    locator_offset = end_offset - locator_size
    if locator_offset < 0:
        raise zipfile.BadZipFile("ZIP64 locator is missing.")
    file_handle.seek(locator_offset)
    locator_bytes = file_handle.read(locator_size)
    if len(locator_bytes) != locator_size:
        raise zipfile.BadZipFile("ZIP64 locator is truncated.")
    signature, disk_number, declared_offset, disk_count = struct.unpack(
        ZIP64_LOCATOR_FORMAT,
        locator_bytes,
    )
    if signature != ZIP64_LOCATOR_SIGNATURE:
        raise zipfile.BadZipFile("ZIP64 locator is missing.")
    if disk_number != 0 or disk_count != 1:
        raise zipfile.BadZipFile("Multi-disk ZIP64 archives are not supported.")
    record_result = _read_zip64_end_record(file_handle, declared_offset)
    if record_result is None:
        record_result = _read_zip64_end_record(
            file_handle,
            locator_offset - zip64_end_record_size,
        )
    if record_result is None:
        raise zipfile.BadZipFile("ZIP64 end record is missing.")
    record, record_offset = record_result
    (
        _signature,
        record_size,
        _created_version,
        _required_version,
        record_disk,
        directory_disk,
        entries_on_disk,
        total_entries,
        directory_size,
        _directory_offset,
    ) = record
    if record_size < zip64_end_record_size - 12:
        raise zipfile.BadZipFile("ZIP64 end record is invalid.")
    if record_disk != 0 or directory_disk != 0 or entries_on_disk != total_entries:
        raise zipfile.BadZipFile("Multi-disk ZIP64 archives are not supported.")
    return int(total_entries), int(directory_size), record_offset


def _read_zip64_end_record(
    file_handle: io.BufferedIOBase | io.RawIOBase,
    offset: int,
) -> tuple[tuple[bytes, int, int, int, int, int, int, int, int, int], int] | None:
    if offset < 0:
        return None
    file_handle.seek(offset)
    zip64_end_record_size = struct.calcsize(ZIP64_END_RECORD_FORMAT)
    record_bytes = file_handle.read(zip64_end_record_size)
    if len(record_bytes) != zip64_end_record_size:
        return None
    record = struct.unpack(ZIP64_END_RECORD_FORMAT, record_bytes)
    return (record, offset) if record[0] == ZIP64_END_RECORD_SIGNATURE else None


def _has_zip64_locator(
    file_handle: io.BufferedIOBase | io.RawIOBase,
    end_offset: int,
) -> bool:
    locator_size = struct.calcsize(ZIP64_LOCATOR_FORMAT)
    locator_offset = end_offset - locator_size
    if locator_offset < 0:
        return False
    file_handle.seek(locator_offset)
    return file_handle.read(len(ZIP64_LOCATOR_SIGNATURE)) == ZIP64_LOCATOR_SIGNATURE


def _validate_central_directory(
    file_handle: io.BufferedIOBase | io.RawIOBase,
    *,
    directory_end_offset: int,
    directory_size: int,
    declared_entries: int,
    limits: ArchiveResourceLimits,
) -> None:
    directory_start = directory_end_offset - directory_size
    if directory_start < 0:
        raise zipfile.BadZipFile("ZIP central directory offset is invalid.")
    directory_header_size = struct.calcsize(CENTRAL_DIRECTORY_FORMAT)
    directory_position = directory_start
    budget = ArchivePlanningBudget(limits)
    actual_entries = 0
    while directory_position < directory_end_offset:
        file_handle.seek(directory_position)
        header_bytes = file_handle.read(directory_header_size)
        if len(header_bytes) != directory_header_size:
            raise zipfile.BadZipFile("ZIP central directory is truncated.")
        header = struct.unpack(CENTRAL_DIRECTORY_FORMAT, header_bytes)
        if header[0] != CENTRAL_DIRECTORY_SIGNATURE:
            raise zipfile.BadZipFile("ZIP central directory entry is invalid.")
        filename_size = int(header[12])
        extra_size = int(header[13])
        comment_size = int(header[14])
        metadata_size = filename_size + extra_size + comment_size
        next_position = directory_position + directory_header_size + metadata_size
        if next_position > directory_end_offset:
            raise zipfile.BadZipFile("ZIP central directory entry is truncated.")
        budget.add_member(
            metadata_bytes=metadata_size,
            name=f"central-directory entry {actual_entries + 1}",
        )
        actual_entries += 1
        directory_position = next_position
    if actual_entries != declared_entries:
        raise zipfile.BadZipFile("ZIP central directory entry count is inconsistent.")


def _enforce_directory_limits(
    total_entries: int,
    directory_size: int,
    limits: ArchiveResourceLimits,
) -> None:
    if total_entries > limits.max_members:
        raise ValidationError(f"ZIP archive exceeds the member limit of {limits.max_members}.")
    if directory_size > limits.max_aggregate_metadata_bytes:
        raise ValidationError(
            f"ZIP central directory exceeds the metadata limit of {limits.max_aggregate_metadata_bytes} bytes.",
        )
