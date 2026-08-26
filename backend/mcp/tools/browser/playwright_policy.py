"""SoAI - Shared Playwright install and launch policy helpers [backend/mcp/tools/browser/playwright_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

from core.bootstrap.playwright_browser_state import is_expected_chromium_installed
from core.bootstrap.runtime_directories import ensure_runtime_directory_environment
from core.browser.playwright_installation import (
    install_chromium_async,
    should_retry_install_after_launch_error,
)
from core.config.protocols import ConfigProtocol
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.meta.paths import get_repo_root
from core.runtime.network_policy import is_offline_mode_enabled
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.validation.integers import is_strict_int
from mcp.tools.offline_policy import build_offline_mode_error

__all__ = (
    "ensure_playwright_browsers_path",
    "ensure_playwright_chromium_available",
    "is_playwright_auto_install_enabled",
    "is_playwright_stay_offline",
    "require_playwright_chromium_ready",
    "resolve_playwright_auto_install_timeout_sec",
    "resolve_playwright_launch_args",
    "should_retry_playwright_auto_install_after_launch_error",
)

LOGGER_NAME = "SoAI.mcp.tools.playwright_policy"
OPERATION = "mcp.browser.playwright_policy.launch_args"


def ensure_playwright_browsers_path() -> None:
    ensure_runtime_directory_environment(get_repo_root())


def resolve_playwright_launch_args() -> list[str]:
    logger = get_logger(LOGGER_NAME)
    launch_args: list[str] = []
    try:
        geteuid = os.geteuid
    except AttributeError:
        geteuid = None
    if os.name != "nt" and geteuid is not None:
        try:
            if geteuid() == 0:
                launch_args.append("--no-sandbox")
        except OSError as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="mcp.browser.playwright_policy.launch_args",
            )
            log_handled_exception(
                logger,
                coerced,
                message="Failed to inspect effective UID for Chromium sandbox flag (non-critical).",
                operation=OPERATION,
                details={},
                level="debug",
            )
    return launch_args


def is_playwright_auto_install_enabled(config: ConfigProtocol) -> bool:
    return bool(config.get_bool("TOOLS.MCP.BROWSER.AUTO_INSTALL"))


def is_playwright_stay_offline(runtime_flags: RuntimeFlagsViewProtocol) -> bool:
    return is_offline_mode_enabled(runtime_flags)


def should_retry_playwright_auto_install_after_launch_error(
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    exception: Exception,
) -> bool:
    return (
        is_playwright_auto_install_enabled(config)
        and not is_playwright_stay_offline(runtime_flags)
        and should_retry_install_after_launch_error(exception)
    )


def resolve_playwright_auto_install_timeout_sec(config: ConfigProtocol) -> int:
    timeout_sec = config.get_int("TOOLS.MCP.BROWSER.AUTO_INSTALL_TIMEOUT_SEC")
    if not is_strict_int(timeout_sec):
        return 7200
    return max(60, min(72_000, int(timeout_sec)))


async def ensure_playwright_chromium_available(
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    force: bool,
) -> None:
    repo_root = get_repo_root()
    browsers_path = ensure_runtime_directory_environment(repo_root).playwright_browsers_path
    if not force and is_expected_chromium_installed(browsers_path=browsers_path):
        return
    if is_playwright_stay_offline(runtime_flags):
        raise build_offline_mode_error(
            tool_name="browser tools",
            capability="playwright chromium auto-install",
            url=None,
        )
    if not is_playwright_auto_install_enabled(config):
        raise ValidationError(
            "Playwright Chromium is missing or incompatible and TOOLS.MCP.BROWSER.AUTO_INSTALL=false.",
        )
    await install_chromium_async(
        python_executable=sys.executable,
        repo_root_path=repo_root,
        timeout_sec=resolve_playwright_auto_install_timeout_sec(config),
        force=force,
    )
    if not is_expected_chromium_installed(browsers_path=browsers_path):
        raise ValidationError("Playwright Chromium auto-install did not produce an install.")


async def require_playwright_chromium_ready(
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
) -> None:
    repo_root = get_repo_root()
    browsers_path = ensure_runtime_directory_environment(repo_root).playwright_browsers_path
    if is_expected_chromium_installed(browsers_path=browsers_path):
        return
    if not is_playwright_auto_install_enabled(config):
        raise ValidationError(
            "Playwright Chromium is not installed and TOOLS.MCP.BROWSER.AUTO_INSTALL=false.",
        )
    await ensure_playwright_chromium_available(config, runtime_flags, force=False)
