"""SoAI - Log compression for rotating handlers [backend/core/logging/handlers/log_compression.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import gzip
import os

from core.errors.exceptions import NotFoundError, StateError
from core.filesystem.open_files import open_binary
from core.logging.protocols import CompressionHandlerProtocol

__all__ = ("CompressionHelper",)


class CompressionHelper:
    def __init__(self, handler: CompressionHandlerProtocol) -> None:
        self._handler = handler

    def apply_suffix(self, path: str) -> str:
        try:
            compress_enabled = bool(self._handler.compress)
        except AttributeError:
            compress_enabled = False
        if not compress_enabled:
            return path
        try:
            suffix = self._handler.compression_suffix
        except AttributeError:
            suffix = ".gz"
        return path if not suffix or path.endswith(suffix) else f"{path}{suffix}"

    def _resolve_existing_archive(self, path: str) -> str | None:
        if os.path.exists(path):
            return path
        try:
            suffix = self._handler.compression_suffix
        except AttributeError:
            suffix = ".gz"
        try:
            compress_enabled = bool(self._handler.compress)
        except AttributeError:
            compress_enabled = False
        if compress_enabled and suffix and path.endswith(suffix):
            stripped = path[: -len(suffix)]
            if os.path.exists(stripped):
                return stripped
        return None

    def remove_destination(self, path: str) -> None:
        target = self.apply_suffix(path)
        if os.path.exists(target):
            os.remove(target)
        elif os.path.exists(path):
            os.remove(path)

    def resolve_source_path(self, path: str) -> str | None:
        try:
            compress_enabled = bool(self._handler.compress)
        except AttributeError:
            compress_enabled = False
        if compress_enabled:
            return self._resolve_existing_archive(self.apply_suffix(path))
        return path if os.path.exists(path) else None

    def compress_and_rotate(self, source: str, dest: str) -> None:
        try:
            compress_enabled = bool(self._handler.compress)
        except AttributeError:
            compress_enabled = False
        target = self.apply_suffix(dest) if compress_enabled else dest
        if compress_enabled:
            if not os.path.exists(source):
                raise NotFoundError(source)
            with (
                open_binary(source, mode="rb") as source_handle,
                gzip.open(target, "wb") as target_handle,
            ):
                target_handle.writelines(source_handle)
            os.remove(source)
            return
        try:
            rotate = self._handler.rotate
        except AttributeError:
            rotate = None
        if not callable(rotate):
            raise StateError("Rotation handler is not available.")
        rotate(source, target)
