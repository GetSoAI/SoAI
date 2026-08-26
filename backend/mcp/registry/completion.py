"""SoAI - MCP completion handlers [backend/mcp/registry/completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.internal_protocols import MCPRegistryManagerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("handle_completion_complete",)


async def handle_completion_complete(
    manager: MCPRegistryManagerProtocol,
    parameters: JSONDict,
) -> JSONDict:
    reference = coerce_json_dict(parameters.get("ref", {})) or {}
    argument = coerce_json_dict(parameters.get("argument", {})) or {}
    values: list[str] = []
    argument_value = argument.get("value")
    if (
        reference.get("type") == "ref/resource"
        and (reference.get("uri") or reference.get("name")) == "soai://models/{model_id}"
        and (argument.get("name") == "model_id")
        and isinstance(argument_value, str)
    ):
        model_information_service = manager.model_information_service
        if model_information_service is None:
            raise MCPJSONRPCError(-32603, "Model information service is not available")
        values = sorted(
            [
                str(model_entry.get("id", ""))
                for model_entry in await model_information_service.model_get_available()
                if str(model_entry.get("id", "")).lower().startswith(argument_value.lower())
            ],
        )
    return {
        "completion": {
            "values": values[:100],
            "total": len(values),
            "hasMore": len(values) > 100,
        },
    }
