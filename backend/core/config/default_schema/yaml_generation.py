"""SoAI - Default config schema YAML generation [backend/core/config/default_schema/yaml_generation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from core.config.yaml_factory import build_roundtrip_yaml
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.open_files import open_text
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = (
    "ensure_default_config_yaml",
    "render_default_config_yaml_text",
)


def render_default_config_yaml_text(schema: ConfigDict) -> str:
    yaml_dump = build_roundtrip_yaml()
    buffer = io.StringIO()
    yaml_dump.dump(schema, buffer)
    return buffer.getvalue()


def ensure_default_config_yaml(
    path: str,
    *,
    schema: ConfigDict,
    logger: LoggerProtocol | None,
) -> bool:
    existing = None
    if os.path.isfile(path):
        try:
            yaml_safe = YAML(typ="safe")
            with open_text(path, encoding="utf-8") as file_handle:
                existing = yaml_safe.load(file_handle)
        except (OSError, ValueError, TypeError, YAMLError):
            existing = None
    if isinstance(existing, dict) and existing == schema:
        return False

    def _writer(handle: io.TextIOBase) -> None:
        yaml_dump = build_roundtrip_yaml()
        yaml_dump.dump(schema, handle)

    backup_path = f"{path}.backup" if os.path.isfile(path) else None
    atomic_write_text(path, _writer, encoding="utf-8", backup_path=backup_path)
    if logger is not None:
        logger.warning("Generated config.default.yaml from code-first schema: %s", path)
    return True
