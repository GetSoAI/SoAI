"""SoAI - Plugin SDK model metadata helpers [backend/plugin_sdk/contracts/metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import open_text
from core.filesystem.path_coercion import coerce_path
from core.serialization.json_parsing import parse_json_dict
from plugin_sdk.contracts.errors import PluginConfigurationError

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput
    from core.types.json import JSONDict

__all__ = (
    "ModelMetadataStore",
    "read_metadata",
)


MODEL_METADATA_UNREADABLE_REASON = "model_metadata_unreadable"


def _unreadable_metadata_error() -> StateError:
    return StateError(
        "Existing model metadata could not be read.",
        details={"reason": MODEL_METADATA_UNREADABLE_REASON},
    )


def _read_metadata_file(path: str, *, strict: bool) -> JSONDict | None:
    try:
        with open_text(path, encoding="utf-8") as handle:
            content = handle.read()
        return parse_json_dict(content, field="plugin metadata")
    except FileNotFoundError:
        return None
    except (OSError, ValidationError) as exception:
        if not strict:
            return None
        raise _unreadable_metadata_error() from exception
    except UnicodeDecodeError as exception:
        if not strict:
            raise
        raise _unreadable_metadata_error() from exception


def read_metadata(path: PathInput, *, strict: bool = False) -> JSONDict | None:
    return _read_metadata_file(coerce_path(path), strict=strict)


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

    def read(self, target_path: PathInput, *, strict: bool = False) -> JSONDict | None:
        return _read_metadata_file(self.resolve(target_path), strict=strict)
