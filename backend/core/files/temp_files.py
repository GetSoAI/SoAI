"""SoAI - Secure temporary file creation helpers [backend/core/files/temp_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
import tempfile
import uuid

from core.errors.exceptions import StateError

__all__ = (
    "acquire_directory_lock",
    "create_persistent_staging_directory",
    "create_secure_temp_directory",
    "create_secure_temp_binary_handle",
    "create_secure_temp_file_descriptor",
    "release_directory_lock",
    "system_temp_directory",
)


def system_temp_directory() -> str:
    return tempfile.gettempdir()


def acquire_directory_lock(path: str) -> bool:
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        return False
    return True


def release_directory_lock(path: str) -> None:
    os.rmdir(path)


def create_persistent_staging_directory(
    *,
    directory: str | None,
    prefix: str,
    suffix: str = "",
) -> str:
    if os.name != "nt":
        return tempfile.mkdtemp(prefix=prefix, suffix=suffix, dir=directory)
    parent_directory = directory if directory is not None else tempfile.gettempdir()
    staging_path = os.path.join(
        parent_directory,
        f"{prefix}{uuid.uuid4().hex}{suffix}",
    )
    os.mkdir(staging_path)
    return staging_path


def create_secure_temp_file_descriptor(
    *,
    directory: str | None,
    prefix: str,
    suffix: str = "",
) -> tuple[int, str]:
    file_descriptor, temp_path = tempfile.mkstemp(
        prefix=prefix,
        suffix=suffix,
        dir=directory,
    )
    try:
        os.chmod(temp_path, 0o600)
    except OSError as exception:
        try:
            os.close(file_descriptor)
        except OSError as close_exception:
            exception.add_note(f"Failed to close temp file descriptor: {close_exception}")
        try:
            os.remove(temp_path)
        except OSError as remove_exception:
            exception.add_note(
                f"Failed to remove temp file after chmod failure: {remove_exception}",
            )
        raise
    return (file_descriptor, temp_path)


def create_secure_temp_binary_handle(
    *,
    directory: str | None,
    prefix: str,
    suffix: str = "",
) -> tuple[io.BufferedRandom, str]:
    file_descriptor, temp_path = create_secure_temp_file_descriptor(
        directory=directory,
        prefix=prefix,
        suffix=suffix,
    )
    try:
        file_handle = os.fdopen(file_descriptor, "w+b")
    except (OSError, ValueError) as exception:
        try:
            os.close(file_descriptor)
        except OSError as close_exception:
            exception.add_note(f"Failed to close temporary file descriptor: {close_exception}")
        try:
            os.remove(temp_path)
        except OSError as remove_exception:
            exception.add_note(f"Failed to remove temporary file: {remove_exception}")
        raise
    if not isinstance(file_handle, io.BufferedRandom):
        invariant_error = StateError(
            "Secure temporary binary handle must be buffered and seekable.",
            operation="core.files.create_secure_temp_binary_handle",
        )
        try:
            file_handle.close()
        except OSError as close_exception:
            invariant_error.add_note(f"Failed to close temporary file: {close_exception}")
        try:
            os.remove(temp_path)
        except OSError as remove_exception:
            invariant_error.add_note(f"Failed to remove temporary file: {remove_exception}")
        raise invariant_error
    return file_handle, temp_path


def create_secure_temp_directory(
    *,
    directory: str | None = None,
    prefix: str = "soai-",
    suffix: str = "",
) -> str:
    temp_path = tempfile.mkdtemp(prefix=prefix, suffix=suffix, dir=directory)
    try:
        os.chmod(temp_path, 0o700)
    except OSError as exception:
        try:
            os.rmdir(temp_path)
        except OSError as remove_exception:
            exception.add_note(
                f"Failed to remove temp directory after chmod failure: {remove_exception}",
            )
        raise
    return temp_path
