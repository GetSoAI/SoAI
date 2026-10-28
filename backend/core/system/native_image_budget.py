"""SoAI - Windows security-check allowance for freshly installed native images [backend/core/system/native_image_budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from collections.abc import Iterable
from dataclasses import dataclass

from core.files.windows_reparse_points import is_windows_reparse_point
from core.filesystem.directory_walk import raise_directory_walk_error
from core.logging.trace import get_logger
from core.platform.os import is_windows

__all__ = (
    "NATIVE_IMAGE_SUFFIXES",
    "WINDOWS_SECURITY_CHECK_SECONDS_PER_IMAGE",
    "NativeImageAllowance",
    "count_native_images",
    "native_image_allowance",
)

WINDOWS_SECURITY_CHECK_SECONDS_PER_IMAGE = 60.0
NATIVE_IMAGE_SUFFIXES = (".dll", ".exe", ".pyd")

LOGGER_NAME = "SoAI.core.system.native_image_budget"


@dataclass(frozen=True, slots=True)
class NativeImageAllowance:
    seconds: float
    ordinary_seconds: float
    native_image_count: int
    inventory_complete: bool
    constrained: bool


def _is_linked_entry(path: str) -> bool:
    status = os.lstat(path)
    return stat.S_ISLNK(status.st_mode) or is_windows_reparse_point(status)


def _collect_root_images(root: str, excluded_names: frozenset[str], images: set[str]) -> None:
    if not os.path.isdir(root):
        if os.path.isfile(root) and root.lower().endswith(NATIVE_IMAGE_SUFFIXES):
            images.add(os.path.normcase(os.path.abspath(root)))
        return
    for base, directories, files in os.walk(root, onerror=raise_directory_walk_error):
        directories[:] = [
            name
            for name in directories
            if name.lower() not in excluded_names and not _is_linked_entry(os.path.join(base, name))
        ]
        for name in files:
            path = os.path.join(base, name)
            if name.lower().endswith(NATIVE_IMAGE_SUFFIXES) and not _is_linked_entry(path):
                images.add(os.path.normcase(os.path.abspath(path)))


def _collect_shallow_images(directory: str, suffixes: tuple[str, ...], images: set[str]) -> None:
    if not os.path.isdir(directory):
        return
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.name.lower().endswith(suffixes) and not _is_linked_entry(entry.path):
                if entry.is_file(follow_symlinks=False):
                    images.add(os.path.normcase(os.path.abspath(entry.path)))


def count_native_images(
    roots: Iterable[str],
    *,
    shallow_roots: Iterable[str] = (),
    shallow_image_suffixes: tuple[str, ...] = NATIVE_IMAGE_SUFFIXES,
    excluded_names: Iterable[str] = (),
    planned_paths: Iterable[str] = (),
) -> int:
    images = {
        os.path.normcase(os.path.abspath(path))
        for path in planned_paths
        if path.lower().endswith(NATIVE_IMAGE_SUFFIXES)
    }
    excluded = frozenset(name.lower() for name in excluded_names)
    for root in roots:
        _collect_root_images(root, excluded, images)
    for directory in shallow_roots:
        _collect_shallow_images(directory, shallow_image_suffixes, images)
    return len(images)


def native_image_allowance(
    ordinary_seconds: float,
    *,
    roots: Iterable[str],
    shallow_roots: Iterable[str] = (),
    shallow_image_suffixes: tuple[str, ...] = NATIVE_IMAGE_SUFFIXES,
    excluded_names: Iterable[str] = (),
    ceiling_seconds: float | None = None,
    planned_paths: Iterable[str] = (),
) -> NativeImageAllowance:
    count = 0
    complete = True
    if is_windows():
        try:
            count = count_native_images(
                roots,
                shallow_roots=shallow_roots,
                shallow_image_suffixes=shallow_image_suffixes,
                excluded_names=excluded_names,
                planned_paths=planned_paths,
            )
        except OSError as exception:
            complete = False
            get_logger(LOGGER_NAME).warning(
                "Native image inventory failed; using the ordinary allowance: %s", exception
            )
    seconds = ordinary_seconds + WINDOWS_SECURITY_CHECK_SECONDS_PER_IMAGE * count
    constrained = ceiling_seconds is not None and seconds > ceiling_seconds
    return NativeImageAllowance(
        seconds=min(seconds, ceiling_seconds) if ceiling_seconds is not None else seconds,
        ordinary_seconds=ordinary_seconds,
        native_image_count=count,
        inventory_complete=complete,
        constrained=constrained,
    )
