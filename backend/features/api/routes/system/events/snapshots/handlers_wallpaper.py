"""SoAI - Snapshot handler for wallpaper status [backend/features/api/routes/system/events/snapshots/handlers_wallpaper.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import WebSocket
from starlette.datastructures import URL

from core.types.json import JSONDict
from features.api.streaming.websocket import WebsocketConnection

__all__ = ("snapshot_wallpaper_status",)


def _websocket_url_to_http(ws_url_string: str) -> str:
    if ws_url_string.startswith("ws://"):
        return f"http://{ws_url_string}"[5:]
    if ws_url_string.startswith("wss://"):
        return f"https://{ws_url_string}"[6:]
    return ws_url_string


async def snapshot_wallpaper_status(
    _data: JSONDict,
    connection: WebsocketConnection,
    ws: WebSocket,
) -> JSONDict:
    wallpaper_manager = connection.api_context.dependencies.webui_manager.wallpaper
    _, mtime, metadata = await wallpaper_manager.get_current_wallpaper_details()
    if not mtime:
        return {"exists": False, "url": None, "metadata": None}
    raw_url = _websocket_url_to_http(str(ws.url_for("serve_wallpaper_file")))
    wallpaper_url = str(URL(raw_url).include_query_params(v=int(mtime)))
    metadata_dict: JSONDict | None = None
    if metadata is not None:
        if isinstance(metadata, dict):
            metadata_dict = metadata
        else:
            model_dump_fn = None
            try:
                model_dump_fn = metadata.model_dump
            except AttributeError:
                model_dump_fn = None
            if callable(model_dump_fn):
                metadata_dict = model_dump_fn()
    return {"exists": True, "url": wallpaper_url, "metadata": metadata_dict}
