"""SoAI - Plugin SDK static variant resource loading [backend/plugin_sdk/contracts/backend_variant_resources.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.files.path_policy import safe_join_relative_under_base_lexical
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.plugins.backend_variant_resources import (
    MAX_BACKEND_VARIANT_RESOURCE_BYTES,
    parse_backend_variant_resource,
    require_backend_variant_resource_name,
)
from core.types.json import JSONDict

__all__ = ("load_backend_variant_options",)


def load_backend_variant_options(plugin_file: str, resource_name: str) -> list[JSONDict]:
    resource = require_backend_variant_resource_name(resource_name)
    path = safe_join_relative_under_base_lexical(
        base_path=os.path.dirname(plugin_file),
        relative_path=resource,
        description="Backend variant metadata",
    )
    with open_regular_binary_no_symlink(path) as source:
        return parse_backend_variant_resource(source.read(MAX_BACKEND_VARIANT_RESOURCE_BYTES + 1))
