"""SoAI - Parent-side plugin worker surface model [backend/plugins/worker/surface.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.types.json import JSONDict, JSONValue
from plugins.worker.payload_fields import (
    read_dict_field,
    read_non_empty_str_field,
    read_optional_str_field,
)

__all__ = ("PluginRuntimeSurface",)


@dataclass(frozen=True, slots=True)
class PluginRuntimeSurface:
    class_fields: JSONDict
    default_configuration: JSONDict
    parameter_schema: JSONDict
    openai_capabilities: JSONDict
    models_directory: str
    log_file_path: str | None

    @classmethod
    def from_payload(cls, payload: JSONDict) -> PluginRuntimeSurface:
        return cls(
            class_fields=read_dict_field(
                payload,
                "class_fields",
                label="Plugin worker surface field",
            ),
            default_configuration=read_dict_field(
                payload,
                "default_configuration",
                label="Plugin worker surface field",
            ),
            parameter_schema=read_dict_field(
                payload,
                "parameter_schema",
                label="Plugin worker surface field",
            ),
            openai_capabilities=read_dict_field(
                payload,
                "openai_capabilities",
                label="Plugin worker surface field",
            ),
            models_directory=read_non_empty_str_field(
                payload,
                "models_directory",
                label="Plugin worker surface field",
            ),
            log_file_path=read_optional_str_field(
                payload,
                "log_file_path",
                label="Plugin worker surface field",
            ),
        )

    def field(self, name: str) -> JSONValue | None:
        return self.class_fields.get(name)
