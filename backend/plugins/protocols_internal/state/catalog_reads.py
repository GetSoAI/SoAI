"""SoAI - Plugin catalog reader ownership state [backend/plugins/protocols_internal/state/catalog_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("PluginCatalogReadState",)


@dataclass(slots=True)
class PluginCatalogReadState:
    users: int = 0
    discovery_owned: bool = False
