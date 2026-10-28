"""SoAI - Descriptor anchored Linux sysfs device acquisition [backend/hardware/gpu_inventory/linux_sysfs_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import os
from collections.abc import Generator
from contextlib import contextmanager

from core.errors.exceptions import StateError, ValidationError
from core.files.secure_open_flags import secure_read_only_open_flags
from core.filesystem.descriptor_io import open_descriptor, read_bounded_descriptor
from core.filesystem.path_coercion import require_direct_entry_name

__all__ = (
    "MAX_SYSFS_OBSERVATION_CHARACTERS",
    "open_sysfs_device_directory",
    "read_sysfs_device_text",
)

MAX_SYSFS_OBSERVATION_CHARACTERS = 65536


@contextmanager
def open_sysfs_device_directory(
    bus_descriptor: int, name: str, *, devices_root: str
) -> Generator[tuple[str, int]]:
    descriptor = open_descriptor(
        require_direct_entry_name(name),
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY,
        dir_fd=bus_descriptor,
    )
    try:
        device_path = _observed_device_path(descriptor, devices_root)
        yield device_path, descriptor
        if _observed_device_path(descriptor, devices_root) != device_path:
            raise ValidationError("Linux sysfs GPU device identity changed during acquisition.")
    finally:
        os.close(descriptor)


def _observed_device_path(descriptor: int, devices_root: str) -> str:
    device_path = os.readlink(f"/proc/self/fd/{descriptor}")
    if device_path.endswith(" (deleted)"):
        raise FileNotFoundError("Linux sysfs GPU device disappeared during acquisition.")
    if not device_path.startswith(f"{devices_root}/"):
        raise ValidationError("Linux device bus device relation escapes actual sysfs scope.")
    return device_path


def read_sysfs_device_text(descriptor: int, name: str) -> str:
    try:
        attribute = open_descriptor(
            require_direct_entry_name(name),
            secure_read_only_open_flags(directory=False),
            dir_fd=descriptor,
        )
    except OSError as exception:
        if exception.errno == errno.ELOOP:
            raise ValidationError(
                "Linux sysfs GPU attribute cannot be a symbolic link."
            ) from exception
        raise
    try:
        try:
            content = read_bounded_descriptor(
                attribute,
                MAX_SYSFS_OBSERVATION_CHARACTERS * 4,
                error_message="Linux sysfs GPU observation exceeds its bounded input size.",
            )
        except StateError as exception:
            raise ValidationError(
                "Linux sysfs GPU observation exceeds its bounded input size."
            ) from exception
        try:
            value = content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError as exception:
            raise ValidationError("Linux sysfs GPU observation is not valid UTF-8.") from exception
        if len(value) > MAX_SYSFS_OBSERVATION_CHARACTERS:
            raise ValidationError("Linux sysfs GPU observation exceeds its bounded input size.")
        return value
    finally:
        os.close(attribute)
