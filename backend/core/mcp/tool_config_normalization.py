"""SoAI - MCP tool config normalization helpers [backend/core/mcp/tool_config_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

__all__ = ("normalize_server_filter",)


def normalize_server_filter(server_configs: Mapping[str, bool] | None) -> dict[str, bool]:
    normalized: dict[str, bool] = {}
    if not isinstance(server_configs, Mapping):
        return normalized
    for server_id, enabled in server_configs.items():
        if not isinstance(server_id, str):
            continue
        normalized_server_id = server_id.strip()
        if not normalized_server_id:
            continue
        if not isinstance(enabled, bool):
            continue
        normalized[normalized_server_id] = enabled
    return normalized
