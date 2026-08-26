"""SoAI - Encryption utilities for Fernet and JWT secret derivation [backend/core/security/encryption.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Sequence
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

from core.config.path_resolution import ConfigPathResolutionError, resolve_path
from core.config.protocols import ConfigProtocol
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.filesystem.file_sync import flush_and_fsync_file
from core.filesystem.open_files import (
    create_binary_owner_only,
    open_regular_binary_no_symlink,
)
from core.logging.trace import get_logger
from core.serialization.base64_values import decode_base64_ascii_urlsafe

__all__ = (
    "EncryptionKeyring",
    "decrypt_data",
    "derive_authentication_secret",
    "encrypt_data",
    "load_or_create_encryption_keyring",
)

LOGGER_NAME = "SoAI.core.security.encryption"
OPERATION = "utils_core.load_or_create_encryption_key"
JWT_SECRET_DERIVATION_PURPOSE = b"soai.webui.jwt-signing-secret.v1"


@dataclass(frozen=True, slots=True)
class EncryptionKeyring:
    fernet: tuple[Fernet, ...]
    authentication_secrets: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.fernet or len(self.fernet) != len(self.authentication_secrets):
            raise StateError("Encryption keyring is invalid.")

    @property
    def primary_authentication_secret(self) -> str:
        return self.authentication_secrets[0]


def _resolve_encryption_key_path(config: ConfigProtocol) -> str:
    key_path = config.require_str("SYSTEM.PATHS.SYSTEM_ENCRYPTION_KEY")
    base_path = config.require_str("SYSTEM.PATHS.BASE")
    try:
        resolved_key_path = resolve_path(key_path, base_path)
    except ConfigPathResolutionError as exception:
        raise ValidationError(str(exception)) from exception
    if resolved_key_path is None:
        raise StateError("Encryption key path resolved to None.")
    return resolved_key_path


def _read_validated_encryption_keys(
    resolved_key_path: str,
    *,
    restrict_permissions: bool,
) -> EncryptionKeyring:
    with open_regular_binary_no_symlink(
        resolved_key_path,
        not_found_message="Encryption key file is missing.",
        symlink_message="Encryption key file must not be a symlink.",
        open_message="Encryption key file could not be opened.",
        inspect_message="Encryption key file could not be inspected.",
        regular_file_message="Encryption key path must be a regular file.",
    ) as file_handle:
        keys_bytes = [line.strip() for line in file_handle if line.strip()]
        if not keys_bytes:
            raise StateError("Encryption key file does not contain usable key material.")
        fernet_instances = tuple(Fernet(key) for key in keys_bytes)
        authentication_secrets = tuple(derive_authentication_secret(key) for key in keys_bytes)
        if restrict_permissions and os.name == "posix":
            os.fchmod(file_handle.fileno(), 0o600)
    return EncryptionKeyring(
        fernet=fernet_instances,
        authentication_secrets=authentication_secrets,
    )


def _remove_partial_encryption_key(
    resolved_key_path: str,
    created_file_status: os.stat_result,
) -> None:
    current_file_status = os.lstat(resolved_key_path)
    if (
        current_file_status.st_dev != created_file_status.st_dev
        or current_file_status.st_ino != created_file_status.st_ino
    ):
        raise OSError("Created encryption key path changed before cleanup.")
    os.unlink(resolved_key_path)


def _create_encryption_key(resolved_key_path: str) -> bytes:
    parent_directory = os.path.dirname(resolved_key_path) or "."
    os.makedirs(parent_directory, exist_ok=True)
    new_key = Fernet.generate_key()
    created_file_status: os.stat_result | None = None
    try:
        with create_binary_owner_only(resolved_key_path) as file_handle:
            created_file_status = os.fstat(file_handle.fileno())
            file_handle.write(new_key + b"\n")
            flush_and_fsync_file(file_handle)
    except OSError:
        if created_file_status is not None:
            try:
                _remove_partial_encryption_key(resolved_key_path, created_file_status)
            except OSError as cleanup_exception:
                log_handled_exception(
                    get_logger(LOGGER_NAME),
                    cleanup_exception,
                    message="Failed to remove a partial encryption key file.",
                    operation=OPERATION,
                    details={"key_path": resolved_key_path},
                    level="critical",
                )
        raise
    return new_key


def derive_authentication_secret(encoded_encryption_key: bytes) -> str:
    key_material = decode_base64_ascii_urlsafe(
        encoded_encryption_key.decode("ascii"),
        error_message="Stored encryption key is invalid.",
    )
    return hmac.new(
        key_material,
        JWT_SECRET_DERIVATION_PURPOSE,
        hashlib.sha256,
    ).hexdigest()


def load_or_create_encryption_keyring(config: ConfigProtocol) -> EncryptionKeyring:
    logger = get_logger(LOGGER_NAME)
    resolved_key_path = _resolve_encryption_key_path(config)
    try:
        if not os.path.lexists(resolved_key_path):
            logger.info(
                "Encryption key not found at %s. Generating a new one...",
                resolved_key_path,
            )
            new_key = _create_encryption_key(resolved_key_path)
            logger.warning(
                "A new encryption key has been generated and saved to %s. Please backup this file!",
                resolved_key_path,
            )
            return EncryptionKeyring(
                fernet=(Fernet(new_key),),
                authentication_secrets=(derive_authentication_secret(new_key),),
            )
        return _read_validated_encryption_keys(
            resolved_key_path,
            restrict_permissions=True,
        )
    except StateError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to load or create encryption key",
            operation=OPERATION,
            details={"key_path": resolved_key_path},
            level="critical",
        )
        raise
    except (OSError, ValueError, ValidationError) as exception:
        log_exception(
            logger,
            exception,
            message="Failed to load or create encryption key",
            operation=OPERATION,
            details={"key_path": resolved_key_path},
            level="critical",
        )
        raise StateError(
            "Encryption key could not be loaded or created.",
            operation=OPERATION,
            cause=exception,
        ) from exception


def encrypt_data(fernets: Sequence[Fernet], data: str | None) -> str | None:
    if data is None:
        return None
    if not fernets:
        raise StateError("No encryption keys are available to encrypt data.")
    return fernets[0].encrypt(data.encode("utf-8")).decode("utf-8")


def decrypt_data(fernets: Sequence[Fernet], encrypted_data: str | None) -> str | None:
    if encrypted_data is None or encrypted_data == "":
        return None
    if not fernets:
        raise StateError("No encryption keys are available to decrypt data.")
    for fernet_instance in fernets:
        try:
            return fernet_instance.decrypt(encrypted_data.encode("utf-8")).decode("utf-8")
        except (InvalidToken, TypeError, ValueError):
            continue
    get_logger(LOGGER_NAME).warning(
        "Failed to decrypt data with any available key; it may be unencrypted or corrupted.",
    )
    raise StateError("Encrypted data could not be decrypted with any available key.")
