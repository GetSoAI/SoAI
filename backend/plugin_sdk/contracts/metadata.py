"""SoAI - Plugin SDK model metadata helpers [backend/plugin_sdk/contracts/metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.open_files import open_text
from core.filesystem.path_coercion import coerce_path
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from plugin_sdk.contracts.errors import PluginConfigurationError

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput
    from core.types.json import JSONDict

__all__ = (
    "ModelMetadataStore",
    "read_metadata",
)


def _write_metadata_atomic(path: PathInput, metadata: JSONDict) -> None:
    resolved = coerce_path(path)

    def _writer(handle: io.TextIOBase) -> None:
        handle.write(serialize_json_compact_stable_strict(metadata))

    atomic_write_text(resolved, _writer, mode="w", encoding="utf-8")


def read_metadata(path: PathInput) -> JSONDict | None:
    resolved = coerce_path(path)
    if not os.path.exists(resolved):
        return None
    try:
        with open_text(resolved, encoding="utf-8") as handle:
            return parse_json_dict(handle.read(), field="plugin metadata")
    except (OSError, ValidationError):
        return None


class ModelMetadataStore:
    def __init__(self, metadata_filename: str = ".soai_model.json") -> None:
        if not metadata_filename or any(
            sep in metadata_filename for sep in (os.sep, os.altsep) if sep
        ):
            raise PluginConfigurationError("Metadata filename must be a single segment.")
        self.metadata_filename = metadata_filename

    def _target_directory(self, target_path: str) -> str:
        if os.path.isdir(target_path):
            return target_path
        directory = os.path.dirname(target_path)
        if not directory:
            raise PluginConfigurationError(
                "Metadata target path must include a directory component.",
            )
        return directory

    def resolve(self, target_path: PathInput) -> str:
        target = coerce_path(target_path)
        directory = self._target_directory(target)
        if os.path.isdir(target):
            return os.path.join(directory, self.metadata_filename)
        filename = os.path.basename(target)
        return os.path.join(directory, f"{filename}{self.metadata_filename}")

    def read(self, target_path: PathInput) -> JSONDict | None:
        path = self.resolve(target_path)
        if not os.path.exists(path):
            return None
        try:
            with open_text(path, encoding="utf-8") as handle:
                return parse_json_dict(handle.read(), field="plugin metadata")
        except (OSError, ValidationError):
            return None
