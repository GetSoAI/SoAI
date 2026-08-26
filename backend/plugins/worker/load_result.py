"""SoAI - Plugin worker load result surface [backend/plugins/worker/load_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.plugins.protocols_instance import PluginInstanceProtocol
from plugins.worker.surface import PluginRuntimeSurface

__all__ = ("PluginWorkerLoadResult",)


@dataclass(frozen=True, slots=True)
class PluginWorkerLoadResult:
    instance: PluginInstanceProtocol
    surface: PluginRuntimeSurface
