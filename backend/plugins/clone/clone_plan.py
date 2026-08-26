"""SoAI - Plugin clone plan structures [backend/plugins/clone/clone_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("ClonePlan",)


@dataclass(frozen=True, slots=True)
class ClonePlan:
    source_plugin_name: str
    source_display_name: str
    target_plugin_name: str
    target_plugin_file: str
    source_models_path: str | None
    source_models_path_exists: bool
    target_models_path: str | None
    clone_models: bool
    clonable_fields: tuple[JSONDict, ...]
