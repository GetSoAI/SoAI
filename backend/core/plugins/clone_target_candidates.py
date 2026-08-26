"""SoAI - Bounded deterministic automatic clone target candidates [backend/core/plugins/clone_target_candidates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterator

from core.errors.exceptions import ValidationError
from core.plugins.portable_identifiers import require_portable_plugin_identifier

__all__ = ("iter_clone_target_candidates",)

MAXIMUM_CLONE_TARGET_CANDIDATES = 10_000
MAXIMUM_PLUGIN_IDENTIFIER_LENGTH = 100


def iter_clone_target_candidates(source_plugin_name: str) -> Iterator[str]:
    source_name = require_portable_plugin_identifier(
        source_plugin_name,
        field_name="source_plugin_name",
    )
    for counter in range(1, MAXIMUM_CLONE_TARGET_CANDIDATES + 1):
        suffix = f"_clone_{counter}"
        base_limit = MAXIMUM_PLUGIN_IDENTIFIER_LENGTH - len(suffix)
        if base_limit < 1:
            raise ValidationError("Clone target suffix exceeds the portable identifier limit.")
        yield f"{source_name[:base_limit]}{suffix}"
