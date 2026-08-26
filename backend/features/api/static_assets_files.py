"""SoAI - Secure static file serving with CSP nonce injection [backend/features/api/static_assets_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import collections
import os
import re
import threading
from typing import ClassVar, override

from fastapi import Response, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from starlette.types import Scope

from core.errors.public_projection import build_error_payload
from core.files.content_types import content_type_is_html
from core.filesystem.open_files import open_binary
from core.logging.trace import get_logger
from core.serialization.base64_values import encode_base64_ascii
from features.api.webui_csp import build_webui_content_security_policy

__all__ = ("SecureStaticFiles",)

LOGGER_NAME = "SoAI.features.api.static_assets_files"
IMMUTABLE_CACHE_MAX_AGE_SECONDS = 31_536_000


class SecureStaticFiles(StaticFiles):
    _HASHED_ASSET_PATTERN = re.compile("-[a-z0-9_-]{6,32}\\.(js|css)$")
    _IMMUTABLE_CACHE = f"public, max-age={IMMUTABLE_CACHE_MAX_AGE_SECONDS}, immutable"
    _NO_CACHE = "no-cache"
    _CSP_HEAD_INJECTION_PATTERN = re.compile(b"(<head[^>]*>)", re.IGNORECASE)
    _MAX_HTML_CACHE_ENTRIES = 16
    _html_content_cache: ClassVar[collections.OrderedDict[str, tuple[bytes, tuple[int, int]]]] = (
        collections.OrderedDict()
    )
    _html_cache_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, *, directory: str | os.PathLike[str]) -> None:
        super().__init__(directory=directory, html=True)

    @staticmethod
    def _generate_nonce() -> str:
        return encode_base64_ascii(os.urandom(16))

    @classmethod
    async def _get_cached_html_content(cls, file_path: str) -> bytes:
        try:
            stat_result = await asyncio.to_thread(os.stat, file_path)
        except OSError:
            return await asyncio.to_thread(_read_binary, file_path)
        identity = (stat_result.st_mtime_ns, stat_result.st_size)
        with cls._html_cache_lock:
            cached = cls._html_content_cache.get(file_path)
            if cached is not None and cached[1] == identity:
                cls._html_content_cache.move_to_end(file_path)
                return cached[0]
        content, read_identity = await asyncio.to_thread(_read_binary_with_identity, file_path)
        if read_identity is None:
            return content
        with cls._html_cache_lock:
            cls._html_content_cache.pop(file_path, None)
            cls._html_content_cache[file_path] = (content, read_identity)
            cls._html_content_cache.move_to_end(file_path)
            while len(cls._html_content_cache) > cls._MAX_HTML_CACHE_ENTRIES:
                cls._html_content_cache.popitem(last=False)
        return content

    def _apply_cache_headers(self, response: Response, path: str) -> Response:
        try:
            media_type = response.media_type
        except AttributeError:
            media_type = None
        content_type: str | None = None
        if media_type:
            content_type = media_type
        else:
            header_value = response.headers.get("content-type")
            if header_value:
                content_type = header_value
        normalized_path = path.casefold()
        is_html = normalized_path.endswith(".html") or content_type_is_html(content_type)
        if is_html or normalized_path.endswith(".json") or normalized_path.endswith(".webmanifest"):
            response.headers["Cache-Control"] = self._NO_CACHE
        elif self._HASHED_ASSET_PATTERN.search(normalized_path):
            response.headers["Cache-Control"] = self._IMMUTABLE_CACHE
        return response

    @override
    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = status.HTTP_200_OK,
    ) -> Response:
        response = FileResponse(
            full_path,
            status_code=status_code,
            stat_result=stat_result,
        )
        if content_type_is_html(response.media_type):
            return response
        return super().file_response(full_path, stat_result, scope, status_code)

    @classmethod
    async def build_html_response_with_nonce(
        cls,
        file_path: str,
        scope: Scope | None = None,
        status_code: int = status.HTTP_200_OK,
    ) -> Response:
        nonce = cls._generate_nonce()
        content = await cls._get_cached_html_content(file_path)
        nonce_meta_tag = f'\n        <meta name="csp-nonce" content="{nonce}" />'.encode()
        match = cls._CSP_HEAD_INJECTION_PATTERN.search(content)
        if match is None:
            get_logger(LOGGER_NAME).error(
                "CSP nonce injection failed: no <head> tag found in %s. Refusing to serve HTML.",
                file_path,
            )
            payload = build_error_payload(
                "Invalid WebUI asset: missing <head> tag in HTML template.",
                code="server_error",
            )
            error_response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=payload,
            )
            if _scope_method_is_head(scope):
                error_response.body = b""
            return error_response
        injection_point = match.end()
        modified_content = content[:injection_point] + nonce_meta_tag + content[injection_point:]
        csp_header = build_webui_content_security_policy(nonce, scope)
        response_body = b"" if _scope_method_is_head(scope) else modified_content
        html_response = Response(
            content=response_body,
            status_code=status_code,
            media_type="text/html; charset=utf-8",
        )
        html_response.headers["Content-Length"] = str(len(modified_content))
        html_response.headers["Cache-Control"] = cls._NO_CACHE
        html_response.headers["Content-Security-Policy"] = csp_header
        return html_response

    @override
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        content_type = response.headers.get("content-type")
        if content_type_is_html(content_type) and isinstance(response, FileResponse):
            return await self.build_html_response_with_nonce(
                str(response.path),
                scope,
                response.status_code,
            )
        return self._apply_cache_headers(response, path)


def _read_binary(path: str) -> bytes:
    with open_binary(path, mode="rb") as handle:
        return handle.read()


def _read_binary_with_identity(path: str) -> tuple[bytes, tuple[int, int] | None]:
    with open_binary(path, mode="rb") as handle:
        initial_stat = os.fstat(handle.fileno())
        content = handle.read()
        final_stat = os.fstat(handle.fileno())
    initial_identity = (initial_stat.st_mtime_ns, initial_stat.st_size)
    final_identity = (final_stat.st_mtime_ns, final_stat.st_size)
    return content, final_identity if initial_identity == final_identity else None


def _scope_method_is_head(scope: Scope | None) -> bool:
    return scope is not None and str(scope.get("method") or "").upper() == "HEAD"
