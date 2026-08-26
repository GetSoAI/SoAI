"""SoAI - MCP client capabilities builder for host-mode connections [backend/mcp/remote/capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_client_capabilities",)


def _create_base_client_capabilities() -> JSONDict:
    return {
        "roots": {"listChanged": False},
        "sampling": {"tools": {}},
    }


def build_client_capabilities(
    host_mode_enabled: bool,
    host_roots_list_changed_enabled: bool,
    host_elicitation_enabled: bool,
    tasks_enabled: bool,
    host_sampling_enabled: bool,
) -> JSONDict:
    capabilities: JSONDict = _create_base_client_capabilities()
    if not host_mode_enabled:
        return capabilities
    capabilities["roots"] = {"listChanged": host_roots_list_changed_enabled}
    if host_elicitation_enabled:
        capabilities["elicitation"] = {"form": {}, "url": {}}
    if tasks_enabled and (host_sampling_enabled or host_elicitation_enabled):
        tasks_caps: JSONDict = {"list": {}, "cancel": {}, "requests": {}}
        if host_sampling_enabled:
            requests_caps = tasks_caps.get("requests")
            if isinstance(requests_caps, dict):
                requests_caps["sampling"] = {"createMessage": {}}
        if host_elicitation_enabled:
            requests_caps = tasks_caps.get("requests")
            if isinstance(requests_caps, dict):
                requests_caps["elicitation"] = {"create": {}}
        capabilities["tasks"] = tasks_caps
    return capabilities
