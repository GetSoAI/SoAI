"""SoAI - Selected saved timeout default upgrades [backend/app/updater/config_timeout_default_upgrade.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from app.config.schema_disk_reconciliation import ConfigPayloadTransformResult
from core.errors.exceptions import ValidationError
from core.timing.constants import (
    BACKGROUND_TIMEOUT_SEC,
    EXTENDED_TIMEOUT_SEC,
    LONG_REQUEST_TIMEOUT_SEC,
)

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("upgrade_selected_timeout_defaults",)

_HISTORICAL_TIMEOUT_DEFAULTS: tuple[tuple[tuple[str, ...], int, int], ...] = (
    (
        ("DATA", "DATABASE", "WRITER", "INIT_TIMEOUT_SEC"),
        30,
        EXTENDED_TIMEOUT_SEC,
    ),
    (
        ("TOOLS", "RAG", "CHROMA_IPC_STARTUP_TIMEOUT_SEC"),
        120,
        LONG_REQUEST_TIMEOUT_SEC,
    ),
    (
        ("TOOLS", "RAG", "WEB", "HTML_PARSE_TIMEOUT"),
        15,
        BACKGROUND_TIMEOUT_SEC,
    ),
    (
        ("TOOLS", "RAG", "WEB", "PDF_PARSE_TIMEOUT"),
        30,
        LONG_REQUEST_TIMEOUT_SEC,
    ),
)


def upgrade_selected_timeout_defaults(payload: ConfigDict) -> ConfigPayloadTransformResult:
    upgraded_payload = deepcopy(payload)
    changed_paths: list[str] = []
    for path, historical_default, current_default in _HISTORICAL_TIMEOUT_DEFAULTS:
        parent = upgraded_payload
        path_is_present = True
        for segment in path[:-1]:
            if segment not in parent:
                path_is_present = False
                break
            nested = parent[segment]
            if not isinstance(nested, dict):
                raise ValidationError(f"Config key '{'.'.join(path[:-1])}' must be a mapping.")
            parent = nested
        if not path_is_present:
            continue
        leaf = path[-1]
        if leaf not in parent:
            continue
        value = parent[leaf]
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValidationError(f"Config key '{'.'.join(path)}' must be numeric.")
        if value == historical_default:
            parent[leaf] = current_default
            changed_paths.append(".".join(path))
    return ConfigPayloadTransformResult(
        data=upgraded_payload,
        changed_paths=tuple(sorted(changed_paths)),
    )
