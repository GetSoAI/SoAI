"""SoAI - Portable ZIP creation validation and size planning [backend/core/archives/zip_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import unicodedata

from core.archives.constants import accumulate_size, validate_member_name
from core.errors.exceptions import PayloadTooLargeError, ValidationError
from core.files.windows_reserved_names import WINDOWS_RESERVED_ZIP_NAMES
from core.validation.integers import require_non_negative_exact_int

__all__ = (
    "PortableZipPathIndex",
    "calculate_zip_archive_upper_bound",
)

_LOCAL_FILE_HEADER_BYTES = 30
_CENTRAL_DIRECTORY_HEADER_BYTES = 46
_ZIP64_LOCAL_EXTRA_BYTES = 20
_ZIP64_CENTRAL_EXTRA_BYTES = 28
_DATA_DESCRIPTOR_BYTES = 24
_ZIP_END_RECORD_BYTES = 22
_ZIP64_END_RECORD_BYTES = 76
_ZIP_CONTROL_ALLOWANCE_BYTES = 1024
_MAX_ZIP_MEMBER_NAME_BYTES = 65_535
_MAX_PORTABLE_SEGMENT_BYTES = 255
_WINDOWS_FORBIDDEN_CHARACTERS = frozenset('<>:"\\|?*')


class PortableZipPathIndex:
    def __init__(self) -> None:
        self._canonical_paths: dict[str, str] = {}
        self._directory_paths: set[str] = set()
        self._file_paths: set[str] = set()
        self._next_root_ordinal: dict[str, int] = {}

    def add(self, member_path: str, *, is_directory: bool) -> str:
        normalized = _validate_portable_member_path(member_path, is_directory=is_directory)
        canonical = unicodedata.normalize("NFC", normalized).casefold()
        self._require_available(normalized, canonical=canonical, is_directory=is_directory)
        self._register(normalized, canonical=canonical, is_directory=is_directory)
        return normalized + ("/" if is_directory else "")

    def add_unique_root(self, member_name: str, *, is_directory: bool) -> str:
        normalized = _validate_portable_member_path(member_name, is_directory=is_directory)
        if "/" in normalized:
            raise ValidationError("ZIP archive root member name must not contain a path separator.")
        root_key = unicodedata.normalize("NFC", normalized).casefold()
        ordinal = self._next_root_ordinal.get(root_key, 1)
        while True:
            candidate = normalized if ordinal == 1 else _append_copy_number(normalized, ordinal)
            _validate_portable_member_path(candidate, is_directory=is_directory)
            canonical = unicodedata.normalize("NFC", candidate).casefold()
            if not self._has_conflict(canonical, is_directory=is_directory):
                self._register(candidate, canonical=canonical, is_directory=is_directory)
                self._next_root_ordinal[root_key] = ordinal + 1
                return candidate + ("/" if is_directory else "")
            ordinal += 1

    def _require_available(
        self,
        normalized: str,
        *,
        canonical: str,
        is_directory: bool,
    ) -> None:
        previous = self._canonical_paths.get(canonical)
        if previous is not None:
            raise ValidationError(
                f"ZIP archive paths conflict across supported filesystems: '{previous}' and '{normalized}'.",
            )
        path_parts = canonical.split("/")
        for index in range(1, len(path_parts)):
            parent = "/".join(path_parts[:index])
            if parent in self._file_paths:
                raise ValidationError(
                    f"ZIP archive path is nested beneath a file: '{normalized}'.",
                )
        if not is_directory and canonical in self._directory_paths:
            raise ValidationError(
                f"ZIP archive file conflicts with an existing directory path: '{normalized}'.",
            )

    def _has_conflict(self, canonical: str, *, is_directory: bool) -> bool:
        if canonical in self._canonical_paths:
            return True
        path_parts = canonical.split("/")
        if any(
            "/".join(path_parts[:index]) in self._file_paths for index in range(1, len(path_parts))
        ):
            return True
        return not is_directory and canonical in self._directory_paths

    def _register(self, normalized: str, *, canonical: str, is_directory: bool) -> None:
        path_parts = canonical.split("/")
        for index in range(1, len(path_parts)):
            self._directory_paths.add("/".join(path_parts[:index]))
        if is_directory:
            self._directory_paths.add(canonical)
        else:
            self._file_paths.add(canonical)
        self._canonical_paths[canonical] = normalized


def _append_copy_number(member_name: str, ordinal: int) -> str:
    stem, separator, extension = member_name.rpartition(".")
    if separator and stem:
        return f"{stem} ({ordinal}).{extension}"
    return f"{member_name} ({ordinal})"


def calculate_zip_archive_upper_bound(
    members: list[tuple[str, int, bool]],
    *,
    maximum_bytes: int,
) -> int:
    maximum = require_non_negative_exact_int(
        maximum_bytes,
        type_message="ZIP archive size limit must be an integer.",
        range_message="ZIP archive size limit must not be negative.",
    )
    total = _ZIP_END_RECORD_BYTES + _ZIP64_END_RECORD_BYTES + _ZIP_CONTROL_ALLOWANCE_BYTES
    for member_path, size_bytes, is_directory in members:
        _validate_portable_member_path(member_path, is_directory=is_directory)
        normalized_size = require_non_negative_exact_int(
            size_bytes,
            type_message=f"ZIP member size must be an integer: {member_path}",
            range_message=f"ZIP member size must not be negative: {member_path}",
        )
        name_bytes = len(member_path.encode("utf-8"))
        payload_bound = _deflate_upper_bound(0 if is_directory else normalized_size)
        member_bound = (
            _LOCAL_FILE_HEADER_BYTES
            + _CENTRAL_DIRECTORY_HEADER_BYTES
            + _ZIP64_LOCAL_EXTRA_BYTES
            + _ZIP64_CENTRAL_EXTRA_BYTES
            + _DATA_DESCRIPTOR_BYTES
            + (name_bytes * 2)
            + payload_bound
        )
        total = accumulate_size(total, member_bound, member_path)
        if total > maximum:
            raise PayloadTooLargeError(
                "File explorer download archive exceeds the configured size limit.",
                details={"maximum_bytes": maximum, "required_bytes": total},
                operation="core.archives.calculate_zip_archive_upper_bound",
            )
    return total


def _deflate_upper_bound(size_bytes: int) -> int:
    return size_bytes + (size_bytes >> 12) + (size_bytes >> 14) + (size_bytes >> 25) + 13


def _validate_portable_member_path(member_path: str, *, is_directory: bool) -> str:
    raw_path = member_path[:-1] if is_directory and member_path.endswith("/") else member_path
    if not raw_path or raw_path != raw_path.strip("/"):
        raise ValidationError("ZIP archive member path must be relative and non-empty.")
    if "\\" in raw_path:
        raise ValidationError(f"ZIP archive member path contains a backslash: '{raw_path}'.")
    validate_member_name(raw_path)
    try:
        encoded = raw_path.encode("utf-8")
    except UnicodeEncodeError as exception:
        raise ValidationError("ZIP archive member path contains invalid Unicode.") from exception
    if len(encoded) > _MAX_ZIP_MEMBER_NAME_BYTES:
        raise ValidationError(f"ZIP archive member path is too long: '{raw_path}'.")
    for segment in raw_path.split("/"):
        _validate_portable_segment(segment, raw_path)
    return raw_path


def _validate_portable_segment(segment: str, member_path: str) -> None:
    if not segment or segment in {".", ".."}:
        raise ValidationError(f"ZIP archive member path is invalid: '{member_path}'.")
    if segment != segment.strip() or segment.endswith((".", " ")):
        raise ValidationError(
            f"ZIP archive member is not portable across supported filesystems: '{member_path}'.",
        )
    if any(character in _WINDOWS_FORBIDDEN_CHARACTERS for character in segment):
        raise ValidationError(
            f"ZIP archive member contains a platform-reserved character: '{member_path}'.",
        )
    if any(ord(character) < 32 for character in segment):
        raise ValidationError(
            f"ZIP archive member contains a control character: '{member_path}'.",
        )
    if len(segment.encode("utf-8")) > _MAX_PORTABLE_SEGMENT_BYTES:
        raise ValidationError(
            f"ZIP archive member segment is too long: '{member_path}'.",
        )
    stem = segment.split(".", maxsplit=1)[0].upper()
    if stem in WINDOWS_RESERVED_ZIP_NAMES:
        raise ValidationError(
            f"ZIP archive member uses a platform-reserved name: '{member_path}'.",
        )
