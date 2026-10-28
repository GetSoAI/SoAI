"""SoAI - Verified workspace file publication receipts [backend/core/files/commit_receipt.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.errors.exceptions import StateError, ValidationError
from core.files.file_identity import FileIdentity
from core.serialization.sha256_hexdigest import is_canonical_sha256_hexdigest
from core.types.json import JSONDict, JSONValue, is_json_dict
from core.validation.record_fields import require_int
from core.validation.requirements import require_nonempty_str

__all__ = ("FileCommitReceipt", "FilePublicationUncertainError", "FileCleanupIncompleteError")


class FilePublicationUncertainError(StateError):
    code: str | int = "file_publication_uncertain"
    http_status = 409
    public_message: str | None = (
        "The file may have been saved, but its final state could not be verified. "
        "Check the destination in Files before uploading again."
    )


class FileCleanupIncompleteError(StateError):
    code: str | int = "file_cleanup_incomplete"
    http_status = 409
    public_message: str | None = (
        "Automatic cleanup could not be completed. "
        "Review the destination in Files before trying again."
    )


@dataclass(frozen=True, slots=True)
class FileCommitReceipt:
    root_path: str
    relative_path: str
    root_identity: tuple[int, int]
    file_identity: FileIdentity
    sha256_hex: str

    def __post_init__(self) -> None:
        if not os.path.isabs(self.root_path):
            raise ValidationError("File receipt root must be absolute.")
        if (
            not self.relative_path
            or os.path.isabs(self.relative_path)
            or bool(os.path.splitdrive(self.relative_path)[0])
            or "\x00" in self.relative_path
            or any(
                part in {"", ".", ".."} for part in self.relative_path.replace("\\", "/").split("/")
            )
        ):
            raise ValidationError("File receipt location must be a relative workspace path.")
        if not self.file_identity.is_regular_file or self.file_identity.size < 0:
            raise ValidationError("File receipt requires a regular file identity.")
        if not is_canonical_sha256_hexdigest(self.sha256_hex):
            raise ValidationError("File receipt requires a canonical SHA-256 digest.")

    @property
    def destination_path(self) -> str:
        return os.path.join(self.root_path, self.relative_path)

    @property
    def virtual_path(self) -> str:
        relative_path = self.relative_path.replace(os.sep, "/")
        return f"/{relative_path}"

    def to_dict(self) -> JSONDict:
        identity = self.file_identity
        return {
            "root_path": self.root_path,
            "relative_path": self.relative_path,
            "root_identity": [self.root_identity[0], self.root_identity[1]],
            "file_identity": {
                "device": identity.device,
                "inode": identity.inode,
                "mode": identity.mode,
                "size": identity.size,
                "modified_ns": identity.modified_ns,
                "identity_timestamp_ns": identity.identity_timestamp_ns,
                "observed_ctime_ns": identity.observed_ctime_ns,
            },
            "sha256_hex": self.sha256_hex,
        }

    @classmethod
    def from_dict(cls, value: JSONValue) -> FileCommitReceipt:
        if not is_json_dict(value) or set(value) != {
            "root_path",
            "relative_path",
            "root_identity",
            "file_identity",
            "sha256_hex",
        }:
            raise ValidationError("File receipt fields are invalid.")
        root_identity = value["root_identity"]
        if not isinstance(root_identity, list) or len(root_identity) != 2:
            raise ValidationError("File receipt root identity is invalid.")
        identity = value["file_identity"]
        if not is_json_dict(identity) or set(identity) != {
            "device",
            "inode",
            "mode",
            "size",
            "modified_ns",
            "identity_timestamp_ns",
            "observed_ctime_ns",
        }:
            raise ValidationError("File receipt file identity is invalid.")
        return cls(
            root_path=require_nonempty_str(value["root_path"], field="root_path"),
            relative_path=require_nonempty_str(value["relative_path"], field="relative_path"),
            root_identity=(
                require_int(root_identity[0], label="device", build_error=ValidationError),
                require_int(root_identity[1], label="inode", build_error=ValidationError),
            ),
            file_identity=FileIdentity(
                device=require_int(identity["device"], label="device", build_error=ValidationError),
                inode=require_int(identity["inode"], label="inode", build_error=ValidationError),
                mode=require_int(identity["mode"], label="mode", build_error=ValidationError),
                size=require_int(identity["size"], label="size", build_error=ValidationError),
                modified_ns=require_int(
                    identity["modified_ns"], label="modified_ns", build_error=ValidationError
                ),
                identity_timestamp_ns=require_int(
                    identity["identity_timestamp_ns"],
                    label="identity_timestamp_ns",
                    build_error=ValidationError,
                ),
                observed_ctime_ns=require_int(
                    identity["observed_ctime_ns"],
                    label="observed_ctime_ns",
                    build_error=ValidationError,
                ),
            ),
            sha256_hex=require_nonempty_str(value["sha256_hex"], field="sha256_hex"),
        )
