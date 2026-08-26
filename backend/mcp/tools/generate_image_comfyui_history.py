"""SoAI - ComfyUI image history parsing [backend/mcp/tools/generate_image_comfyui_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.tools.generate_image_config import ComfyUIImageSettings

__all__ = ("extract_comfyui_history_image_reference",)


def extract_comfyui_history_image_reference(
    history: JSONDict,
    settings: ComfyUIImageSettings,
    prompt_id: str,
) -> JSONDict | None:
    entry = history.get(prompt_id)
    if not isinstance(entry, dict):
        return None
    outputs = entry.get("outputs")
    if isinstance(outputs, dict):
        if settings.output_node_ids:
            for node_id in settings.output_node_ids:
                image = _first_image_from_output(outputs.get(node_id))
                if image is not None:
                    return image
        for output in outputs.values():
            image = _first_image_from_output(output)
            if image is not None:
                return image
    _raise_for_terminal_history_without_image(entry)
    return None


def _first_image_from_output(output: JSONValue | None) -> JSONDict | None:
    if not isinstance(output, dict):
        return None
    images = output.get("images")
    if not isinstance(images, list) or not images:
        return None
    image = images[0]
    return image if isinstance(image, dict) else None


def _raise_for_terminal_history_without_image(entry: JSONDict) -> None:
    status = entry.get("status")
    if not isinstance(status, dict):
        return
    if _status_has_execution_error(status):
        raise MCPToolError(-32603, "Image generation provider failed while executing the workflow.")
    completed = status.get("completed")
    status_text = status.get("status_str")
    if completed is True or status_text == "success":
        raise MCPToolError(
            -32603,
            "Image generation provider completed without returning an image.",
        )
    if status_text in {"error", "failed"}:
        raise MCPToolError(-32603, "Image generation provider failed while executing the workflow.")


def _status_has_execution_error(status: JSONDict) -> bool:
    messages = status.get("messages")
    if not isinstance(messages, list):
        return False
    for message in messages:
        if isinstance(message, list | tuple) and message and message[0] == "execution_error":
            return True
    return False
