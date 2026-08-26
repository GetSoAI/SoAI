"""SoAI - WebUI static asset serving with CSP injection [backend/features/api/static_assets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI, Response, status
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocketClose

from core.config.protocols import ConfigProtocol
from core.files.path_policy import safe_join_relative_under_base
from core.logging.trace import get_logger
from features.api.static_assets_files import SecureStaticFiles

__all__ = (
    "SecureStaticFiles",
    "WebUIStaticDispatcher",
    "configure_webui_static_assets",
)

LOGGER_NAME = "SoAI.features.api.static_assets"


def _select_static_directory(
    directories: tuple[str, ...],
    request_path: str,
) -> str:
    if not request_path:
        return directories[0]
    for candidate_directory in directories:
        try:
            candidate_path = safe_join_relative_under_base(
                base_path=candidate_directory,
                relative_path=request_path,
                description="WebUI static asset",
            )
        except ValueError:
            return directories[0]
        if os.path.isfile(candidate_path) or os.path.isfile(
            os.path.join(candidate_path, "index.html")
        ):
            return candidate_directory
    return directories[0]


class WebUIStaticDispatcher:
    def __init__(self) -> None:
        self._apps_by_directory: dict[str, SecureStaticFiles] = {}
        self._lock = asyncio.Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "websocket":
            await WebSocketClose()(scope, receive, send)
            return
        directories: tuple[str, ...] | None = None
        app = scope.get("app")
        if app is None:
            state = None
        else:
            try:
                state = app.state
            except AttributeError:
                state = None
        if state is None:
            directory = None
        else:
            configured_directories: tuple[str, ...] | None
            try:
                configured_directories = state.webui_static_directories
            except AttributeError:
                configured_directories = None
            if isinstance(configured_directories, tuple):
                validated_directories: list[str] = []
                for configured_directory in configured_directories:
                    if not isinstance(configured_directory, str):
                        validated_directories = []
                        break
                    validated_directories.append(configured_directory)
                if validated_directories:
                    directories = tuple(validated_directories)
        if not isinstance(directories, tuple) or not directories:
            response = Response(status_code=status.HTTP_404_NOT_FOUND)
            await response(scope, receive, send)
            return
        request_path = str(scope.get("path", "")).lstrip("/")
        directory = _select_static_directory(directories, request_path)
        static_app = self._apps_by_directory.get(directory)
        if static_app is None:
            async with self._lock:
                static_app = self._apps_by_directory.get(directory)
                if static_app is None:
                    static_app = SecureStaticFiles(directory=directory)
                    self._apps_by_directory[directory] = static_app
        await static_app(scope, receive, send)


def configure_webui_static_assets(app_obj: FastAPI, config_obj: ConfigProtocol) -> None:
    path_value = config_obj.require_str("SERVER.WEBUI.PATH")
    static_webui_path = os.path.abspath(os.path.expanduser(path_value))
    fallback_value = config_obj.get("SERVER.WEBUI.FALLBACK_PATHS")
    if fallback_value is None:
        fallback_paths: tuple[str, ...] = ()
    elif isinstance(fallback_value, list):
        resolved_fallback_paths: list[str] = []
        for fallback_path in fallback_value:
            if not isinstance(fallback_path, str) or not fallback_path:
                raise TypeError("SERVER.WEBUI.FALLBACK_PATHS must be an array of paths.")
            resolved_fallback_paths.append(os.path.abspath(os.path.expanduser(fallback_path)))
        fallback_paths = tuple(resolved_fallback_paths)
    else:
        raise TypeError("SERVER.WEBUI.FALLBACK_PATHS must be an array of paths.")
    try:
        state = app_obj.state
    except AttributeError:
        state = None
    if state is None:
        return
    desired_directory = static_webui_path if os.path.isdir(static_webui_path) else None
    try:
        router = app_obj.router
    except AttributeError:
        return
    try:
        existing_dispatcher = state.webui_static_dispatcher
    except AttributeError:
        existing_dispatcher = None
    dispatcher = (
        existing_dispatcher if isinstance(existing_dispatcher, WebUIStaticDispatcher) else None
    )
    if dispatcher is None:
        dispatcher = WebUIStaticDispatcher()
        state.webui_static_dispatcher = dispatcher
    router.default = dispatcher
    if desired_directory is not None:
        state.webui_static_directory = desired_directory
        state.webui_static_directories = (desired_directory, *fallback_paths)
        get_logger(LOGGER_NAME).info("Serving WebUI from %s", static_webui_path)
    else:
        state.webui_static_directory = None
        state.webui_static_directories = ()
        get_logger(LOGGER_NAME).warning(
            "WebUI path %s does not exist. WebUI assets are not available.",
            static_webui_path,
        )
