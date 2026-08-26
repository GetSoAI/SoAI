"""SoAI - Secure file explorer copy error coercion [backend/features/file_explorer/secure_ops/copy_error_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import NoReturn

from core.errors.exceptions import NotFoundError, StateError, ValidationError

__all__ = (
    "raise_copy_directory_exception",
    "raise_copy_file_exception",
)


def raise_copy_file_exception(
    exception: Exception,
    *,
    source_path: str,
    operation: str,
    os_error_message: str,
) -> NoReturn:
    if isinstance(exception, FileNotFoundError):
        raise NotFoundError(
            f"Source file not found: '{os.path.basename(source_path)}'.",
            operation=operation,
        ) from exception
    if isinstance(exception, FileExistsError):
        raise ValidationError(
            "Destination path already exists.",
            operation=operation,
        ) from exception
    if isinstance(exception, OSError):
        raise StateError(
            os_error_message,
            operation=operation,
        ) from exception
    raise exception


def raise_copy_directory_exception(
    exception: Exception,
    *,
    operation: str,
    not_found_message: str,
    os_error_message: str,
) -> NoReturn:
    if isinstance(exception, FileNotFoundError):
        raise NotFoundError(
            not_found_message,
            operation=operation,
        ) from exception
    if isinstance(exception, FileExistsError):
        raise ValidationError(
            "Destination path already exists.",
            operation=operation,
        ) from exception
    if isinstance(exception, OSError):
        raise StateError(
            os_error_message,
            operation=operation,
        ) from exception
    raise exception
