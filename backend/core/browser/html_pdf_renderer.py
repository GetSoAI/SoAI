"""SoAI - Headless Chromium HTML to PDF renderer [backend/core/browser/html_pdf_renderer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from html import escape
from urllib.parse import urlparse
from urllib.request import pathname2url, url2pathname

from playwright.async_api import Error, Route, async_playwright

from core.bootstrap.playwright_browser_state import is_expected_chromium_installed
from core.bootstrap.runtime_directories import ensure_runtime_directory_environment
from core.browser.playwright_installation import install_chromium_async
from core.errors.exceptions import SoAITimeoutError, ValidationError
from core.errors.external_service_exception import ExternalServiceError
from core.files.locking import async_guarded_file_lock
from core.filesystem.open_files import open_text
from core.meta.paths import get_repo_root

__all__ = (
    "HtmlPdfRenderRequest",
    "render_html_file_to_pdf",
)


@dataclass(frozen=True, slots=True)
class HtmlPdfRenderRequest:
    html_path: str
    stylesheet_path: str | None
    asset_root: str | None
    header_template: str
    footer_template: str
    timeout_sec: int


def _stylesheet_link_url(path: str) -> str:
    return f"file://{pathname2url(os.path.abspath(path))}"


def _insert_stylesheet_link(document_html: str, stylesheet_path: str) -> str:
    head_close = document_html.lower().find("</head>")
    if head_close < 0:
        raise ValidationError("PDF export HTML document is missing a head element.")
    href = escape(_stylesheet_link_url(stylesheet_path), quote=True)
    link = f'<link rel="stylesheet" href="{href}">'
    return f"{document_html[:head_close]}{link}{document_html[head_close:]}"


def _resolve_launch_args() -> list[str]:
    if os.name == "nt":
        return []
    try:
        if os.geteuid() == 0:
            return ["--no-sandbox"]
    except AttributeError:
        return []
    except OSError:
        return []
    return []


async def _ensure_chromium_available() -> None:
    repo_root = get_repo_root()
    runtime_environment = ensure_runtime_directory_environment(repo_root)
    browsers_path = runtime_environment.playwright_browsers_path
    if is_expected_chromium_installed(browsers_path=browsers_path):
        return
    lock_path = os.path.join(runtime_environment.locks_path, "playwright-chromium-install.lock")
    async with async_guarded_file_lock(lock_path, timeout=600.0):
        if is_expected_chromium_installed(browsers_path=browsers_path):
            return
        await install_chromium_async(
            python_executable=sys.executable,
            repo_root_path=repo_root,
            timeout_sec=600,
            force=False,
        )


def _is_contained_path(candidate: str, allowed_roots: tuple[str, ...]) -> bool:
    return any(
        candidate == root or candidate.startswith(root + os.sep)
        for root in (os.path.realpath(entry) for entry in allowed_roots)
    )


def _is_allowed_file_request(request_url: str, allowed_roots: tuple[str, ...]) -> bool:
    parsed = urlparse(request_url)
    if parsed.scheme != "file":
        return False
    return _is_contained_path(os.path.realpath(url2pathname(parsed.path)), allowed_roots)


def _require_allowed_file(path: str, allowed_roots: tuple[str, ...], message: str) -> str:
    candidate = os.path.realpath(path)
    if not _is_contained_path(candidate, allowed_roots):
        raise ValidationError(message)
    if not os.path.isfile(candidate):
        raise ValidationError(message)
    return candidate


async def _block_untrusted_request(route: Route, allowed_roots: tuple[str, ...]) -> None:
    request_url = route.request.url
    if request_url.startswith("data:") or request_url.startswith("about:"):
        await route.continue_()
        return
    if _is_allowed_file_request(request_url, allowed_roots):
        await route.continue_()
        return
    await route.abort()


async def _render_once(request: HtmlPdfRenderRequest) -> bytes:
    if not os.path.isfile(request.html_path):
        raise ValidationError("HTML export file is missing.")
    document_root = os.path.dirname(os.path.realpath(request.html_path))
    allowed_roots = (
        (document_root,) if request.asset_root is None else (document_root, request.asset_root)
    )
    stylesheet_path = ""
    if request.stylesheet_path is not None:
        stylesheet_path = _require_allowed_file(
            request.stylesheet_path,
            allowed_roots,
            "PDF render stylesheet is missing.",
        )
    with open_text(request.html_path, mode="r", encoding="utf-8", errors="strict") as handle:
        document_html = handle.read()
    if stylesheet_path:
        document_html = _insert_stylesheet_link(document_html, stylesheet_path)
    await _ensure_chromium_available()
    display_header_footer = bool(request.header_template) or bool(request.footer_template)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=_resolve_launch_args(),
        )
        try:
            context = await browser.new_context(
                java_script_enabled=False,
                bypass_csp=False,
                ignore_https_errors=False,
                viewport={"width": 794, "height": 1123},
            )
            try:
                page = await context.new_page()
                page.set_default_timeout(float(request.timeout_sec * 1000))
                page.set_default_navigation_timeout(float(request.timeout_sec * 1000))

                async def route_handler(route: Route) -> None:
                    await _block_untrusted_request(route, allowed_roots)

                await page.route("**/*", route_handler)
                await page.set_content(
                    document_html,
                    wait_until="load",
                    timeout=float(request.timeout_sec * 1000),
                )
                await page.emulate_media(media="print")
                return await page.pdf(
                    format="A4",
                    print_background=True,
                    display_header_footer=display_header_footer,
                    header_template=request.header_template,
                    footer_template=request.footer_template,
                    margin={
                        "top": "18mm",
                        "right": "14mm",
                        "bottom": "16mm",
                        "left": "14mm",
                    },
                )
            finally:
                await context.close()
        finally:
            await browser.close()


async def render_html_file_to_pdf(request: HtmlPdfRenderRequest) -> bytes:
    if request.timeout_sec <= 0:
        raise ValidationError("PDF render timeout must be positive.")
    try:
        async with asyncio.timeout(request.timeout_sec):
            return await _render_once(request)
    except TimeoutError as exception:
        raise SoAITimeoutError("Chromium PDF rendering timed out.") from exception
    except Error as exception:
        raise ExternalServiceError("Chromium PDF rendering failed.") from exception
