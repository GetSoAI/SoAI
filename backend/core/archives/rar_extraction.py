"""SoAI - RAR archive member validation and extraction [backend/core/archives/rar_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.archives.constants import validate_member_name
from core.archives.errors import ArchivePathTraversalError
from core.archives.reservations import (
    DiskReservationRequest,
    open_disk_reservation,
    open_write_claim,
)
from core.errors.exceptions import StateError, ValidationError
from core.files.path_policy import ensure_path_within_base_lexical
from core.files.protocols_archives import RarArchiveMemberProtocol, RarFileProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.validation.requirements import require_non_negative_exact_int

__all__ = ("safe_rar_extract_members",)

MAX_RAR_MEMBER_NAME_LENGTH: int = 1024


def safe_rar_extract_members(
    archive: RarFileProtocol,
    temp_dir: str,
    *,
    reservation_provider: StorageManagerProtocol,
) -> None:
    members = archive.infolist()
    temp_dir_abs = os.path.abspath(temp_dir)
    total_uncompressed = _validate_rar_members(members, temp_dir_abs)
    with open_disk_reservation(
        reservation_provider,
        requests=(DiskReservationRequest(path=temp_dir_abs, required_bytes=total_uncompressed),),
        operation="core.archives.rar_extraction.extract",
        details={"temp_dir": temp_dir_abs},
    ) as reservation:
        with open_write_claim(reservation, size_bytes=total_uncompressed) as claim:
            for member in members:
                if member.isdir():
                    continue
                archive.extract(member, path=temp_dir_abs)
            if claim is not None:
                claim.commit()


def _validate_rar_members(members: list[RarArchiveMemberProtocol], temp_dir_abs: str) -> int:
    total_uncompressed = 0
    for member in members:
        _validate_rar_member_metadata(member)
        member_size = _coerce_rar_member_size(member)
        total_uncompressed += member_size
        _validate_rar_member_path(member, temp_dir_abs)
    return total_uncompressed


def _validate_rar_member_metadata(member: RarArchiveMemberProtocol) -> None:
    if not isinstance(member, RarArchiveMemberProtocol):
        raise StateError(
            "RAR archive parsing is unavailable because archive entry metadata is invalid.",
        )


def _coerce_rar_member_size(member: RarArchiveMemberProtocol) -> int:
    if member.file_size is None:
        return 0
    return require_non_negative_exact_int(
        member.file_size,
        type_message="RAR archive contains invalid member size.",
        range_message="RAR archive contains invalid negative member size.",
    )


def _validate_rar_member_path(member: RarArchiveMemberProtocol, temp_dir_abs: str) -> None:
    if not isinstance(member.filename, str) or not member.filename:
        raise ValidationError("RAR archive contains invalid member filename.")
    if len(member.filename) > MAX_RAR_MEMBER_NAME_LENGTH:
        raise ValidationError("RAR archive entry name too long")
    if member.file_redir is not None:
        raise ValidationError("RAR archive contains redirected entries which are not allowed")
    is_symlink = member.is_symlink
    if callable(is_symlink) and is_symlink():
        raise ValidationError("RAR archive contains symlink entries which are not allowed")
    if is_symlink is True:
        raise ValidationError("RAR archive contains symlink entries which are not allowed")
    try:
        normalized_member_name = validate_member_name(member.filename)
    except ArchivePathTraversalError as exception:
        raise ValidationError(
            f"RAR archive contains path traversal attempt: {member.filename}",
        ) from exception
    member_path = os.path.normpath(os.path.join(temp_dir_abs, normalized_member_name))
    try:
        ensure_path_within_base_lexical(
            temp_dir_abs,
            member_path,
            description="RAR archive member path",
            error_cls=ValidationError,
        )
    except ValidationError as exception:
        raise ValidationError(
            f"RAR archive contains path traversal attempt: {member.filename}",
        ) from exception
