"""SoAI - Config save outcome type [backend/app/config/save_outcome.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from ruamel.yaml.comments import CommentedMap

from core.config.types import KnownFileState

__all__ = ("ConfigSaveOutcome",)


@dataclass(frozen=True, slots=True)
class ConfigSaveOutcome:
    config_name: str
    config_path: str
    lock_path: str
    backup_path: str
    did_exist_before_save: bool
    previous_known_state: KnownFileState | None
    previous_revision: int | None
    previous_cached_snapshot: CommentedMap | None
    content_hash: str | None
    revision: int
