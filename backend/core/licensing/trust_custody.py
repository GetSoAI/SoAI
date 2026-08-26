"""SoAI - Licensing root trust custody [backend/core/licensing/trust_custody.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.filesystem.open_files import open_regular_binary_no_symlink

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput

MAXIMUM_LICENSING_TRUST_FILE_BYTES = 131_072


def _file_identity_unchanged(
    initial: os.stat_result,
    final: os.stat_result,
    read_length: int,
) -> bool:
    return (
        initial.st_dev == final.st_dev
        and initial.st_ino == final.st_ino
        and initial.st_size == final.st_size
        and read_length == initial.st_size
    )


def read_licensing_trust_file(path: PathInput, *, private: bool) -> bytes:
    with open_regular_binary_no_symlink(
        path,
        not_found_message="Required licensing trust file is missing.",
        symlink_message="Licensing trust file must not be a symbolic link.",
        open_message="Licensing trust file could not be opened.",
        inspect_message="Licensing trust file could not be inspected.",
        regular_file_message="Licensing trust file must be regular.",
    ) as handle:
        initial = os.fstat(handle.fileno())
        forbidden = 0o077 if private else 0o022
        if os.name != "nt" and stat.S_IMODE(initial.st_mode) & forbidden:
            raise ValueError("Licensing trust file permissions are unsafe.")
        content = handle.read(MAXIMUM_LICENSING_TRUST_FILE_BYTES + 1)
        final = os.fstat(handle.fileno())
    if (
        not content
        or len(content) > MAXIMUM_LICENSING_TRUST_FILE_BYTES
        or not _file_identity_unchanged(initial, final, len(content))
    ):
        raise ValueError("Licensing trust file content is invalid.")
    return content


def load_licensing_root_private_key(
    private_path: PathInput,
    password_path: PathInput,
    expected_public: bytes,
) -> Ed25519PrivateKey:
    private_bytes = read_licensing_trust_file(private_path, private=True)
    password = read_licensing_trust_file(password_path, private=True).rstrip(b"\r\n")
    if not password:
        raise ValueError("Licensing root private-key password is empty.")
    loaded = serialization.load_pem_private_key(private_bytes, password=password)
    if not isinstance(loaded, Ed25519PrivateKey):
        raise TypeError("Licensing root private key is not Ed25519.")
    if loaded.public_key().public_bytes_raw() != expected_public:
        raise ValueError("Licensing root private and public keys do not match.")
    return loaded


__all__ = (
    "MAXIMUM_LICENSING_TRUST_FILE_BYTES",
    "load_licensing_root_private_key",
    "read_licensing_trust_file",
)
