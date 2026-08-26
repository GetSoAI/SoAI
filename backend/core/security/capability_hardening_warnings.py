"""SoAI - Optional capability security hardening findings [backend/core/security/capability_hardening_warnings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.protocols import ConfigProtocol
from core.security.hardening_types import SecurityHardeningIssue

__all__ = ("collect_capability_hardening_issues",)


def collect_capability_hardening_issues(
    config: ConfigProtocol,
    *,
    network_exposed: bool,
) -> tuple[SecurityHardeningIssue, ...]:
    issues: list[SecurityHardeningIssue] = []
    mcp_enabled = config.get_bool("TOOLS.MCP.ENABLED")
    webui_enabled = config.get_bool("SERVER.HTTP.ENABLED") and config.get_bool(
        "SERVER.WEBUI.ENABLED"
    )

    if network_exposed and mcp_enabled and config.get_bool("TOOLS.MCP.SHELL.ENABLED"):
        issues.append(
            SecurityHardeningIssue(
                issue_id="mcp_shell_enabled",
                message=(
                    "MCP shell is enabled on a network-exposed deployment, allowing command "
                    "execution via TOOLS.MCP. Disable it unless callers are trusted. "
                    "TOOLS.MCP.SHELL.COMMAND_BLACKLIST is not a security boundary."
                ),
                config_keys=(
                    "TOOLS.MCP.ENABLED",
                    "TOOLS.MCP.SHELL.ENABLED",
                    "TOOLS.MCP.SHELL.COMMAND_BLACKLIST",
                ),
            )
        )
    if network_exposed and webui_enabled and config.get_bool("SERVER.WEBUI.TERMINAL.ENABLED"):
        issues.append(
            SecurityHardeningIssue(
                issue_id="webui_terminal_enabled",
                message=(
                    "WebUI terminal access is enabled on a network-exposed deployment, "
                    "increasing the impact of an authentication or browser compromise."
                ),
                config_keys=(
                    "SERVER.WEBUI.ENABLED",
                    "SERVER.WEBUI.TERMINAL.ENABLED",
                ),
            )
        )
    if mcp_enabled and not config.get_bool("TOOLS.MCP.FILE_GUARD_READ_BEFORE_WRITE.ENABLED"):
        issues.append(
            SecurityHardeningIssue(
                issue_id="mcp_file_read_before_write_guard_disabled",
                message=(
                    "MCP file operations can write without the read-before-write guard. "
                    "Enable the guard to reduce stale or prompt-injected file mutations."
                ),
                config_keys=(
                    "TOOLS.MCP.ENABLED",
                    "TOOLS.MCP.FILE_GUARD_READ_BEFORE_WRITE.ENABLED",
                ),
            )
        )
    if mcp_enabled and not config.get_bool("TOOLS.MCP.WEB_FETCH.BLOCK_PRIVATE_NETWORK_EGRESS"):
        issues.append(
            SecurityHardeningIssue(
                issue_id="mcp_web_fetch_private_network_egress_not_blocked",
                message=(
                    "MCP web_fetch can egress to private network ranges. Enable private-network "
                    "egress blocking to reduce SSRF risk."
                ),
                config_keys=(
                    "TOOLS.MCP.ENABLED",
                    "TOOLS.MCP.WEB_FETCH.BLOCK_PRIVATE_NETWORK_EGRESS",
                ),
            )
        )
    if mcp_enabled and not config.get_bool("TOOLS.MCP.HTTP_REQUEST.BLOCK_PRIVATE_NETWORK_EGRESS"):
        issues.append(
            SecurityHardeningIssue(
                issue_id="mcp_http_request_private_network_egress_not_blocked",
                message=(
                    "MCP http_request can egress to private network ranges. Enable "
                    "private-network egress blocking to reduce SSRF risk."
                ),
                config_keys=(
                    "TOOLS.MCP.ENABLED",
                    "TOOLS.MCP.HTTP_REQUEST.BLOCK_PRIVATE_NETWORK_EGRESS",
                ),
            )
        )
    browser_enabled = mcp_enabled and config.get_bool("TOOLS.MCP.BROWSER.ENABLED")
    if browser_enabled and not config.get_bool("TOOLS.MCP.BROWSER.BLOCK_ADS"):
        issues.append(
            SecurityHardeningIssue(
                issue_id="mcp_browser_adblock_disabled",
                message=(
                    "MCP browser ad blocking is disabled; the controlled browser can load "
                    "malvertising and scam advertisements."
                ),
                config_keys=(
                    "TOOLS.MCP.ENABLED",
                    "TOOLS.MCP.BROWSER.ENABLED",
                    "TOOLS.MCP.BROWSER.BLOCK_ADS",
                ),
            )
        )
    rag_browser_render_enabled = (
        config.get_bool("TOOLS.RAG.ENABLED")
        and config.get_bool("TOOLS.RAG.WEB.ENABLED")
        and (
            config.get_bool("TOOLS.RAG.WEB.BROWSER_RENDER_ON_TIMEOUT_ENABLED")
            or config.get_bool("TOOLS.RAG.WEB.BROWSER_RENDER_ON_HTTP_ERROR_ENABLED")
        )
    )
    if rag_browser_render_enabled and not config.get_bool("TOOLS.RAG.WEB.BROWSER_RENDER_BLOCK_ADS"):
        issues.append(
            SecurityHardeningIssue(
                issue_id="rag_browser_render_adblock_disabled",
                message=(
                    "RAG browser-render ad blocking is disabled; rendered pages can load "
                    "malvertising and scam advertisements."
                ),
                config_keys=(
                    "TOOLS.RAG.ENABLED",
                    "TOOLS.RAG.WEB.ENABLED",
                    "TOOLS.RAG.WEB.BROWSER_RENDER_ON_TIMEOUT_ENABLED",
                    "TOOLS.RAG.WEB.BROWSER_RENDER_ON_HTTP_ERROR_ENABLED",
                    "TOOLS.RAG.WEB.BROWSER_RENDER_BLOCK_ADS",
                ),
            )
        )
    if (
        mcp_enabled
        and config.get_bool("TOOLS.MCP.GENERATE_IMAGE.ENABLED")
        and not config.get_bool("TOOLS.MCP.GENERATE_IMAGE.BLOCK_PRIVATE_NETWORK_EGRESS")
    ):
        issues.append(
            SecurityHardeningIssue(
                issue_id="mcp_generate_image_private_network_egress_not_blocked",
                message=(
                    "MCP generate_image can egress to private network ranges. Enable "
                    "private-network egress blocking to reduce SSRF risk."
                ),
                config_keys=(
                    "TOOLS.MCP.ENABLED",
                    "TOOLS.MCP.GENERATE_IMAGE.ENABLED",
                    "TOOLS.MCP.GENERATE_IMAGE.BLOCK_PRIVATE_NETWORK_EGRESS",
                ),
            )
        )
    if (
        mcp_enabled
        and config.get_bool("TOOLS.MCP.WEATHER.ENABLED")
        and not config.get_bool("TOOLS.MCP.WEATHER.BLOCK_PRIVATE_NETWORK_EGRESS")
    ):
        issues.append(
            SecurityHardeningIssue(
                issue_id="mcp_weather_private_network_egress_not_blocked",
                message=(
                    "MCP weather can egress to private network ranges. Enable private-network "
                    "egress blocking to reduce SSRF risk."
                ),
                config_keys=(
                    "TOOLS.MCP.ENABLED",
                    "TOOLS.MCP.WEATHER.ENABLED",
                    "TOOLS.MCP.WEATHER.BLOCK_PRIVATE_NETWORK_EGRESS",
                ),
            )
        )
    if (
        mcp_enabled
        and config.get_bool("TOOLS.MCP.NEWS.ENABLED")
        and not config.get_bool("TOOLS.MCP.NEWS.BLOCK_PRIVATE_NETWORK_EGRESS")
    ):
        issues.append(
            SecurityHardeningIssue(
                issue_id="mcp_news_private_network_egress_not_blocked",
                message=(
                    "MCP news can egress to private network ranges. Enable private-network "
                    "egress blocking to reduce SSRF risk."
                ),
                config_keys=(
                    "TOOLS.MCP.ENABLED",
                    "TOOLS.MCP.NEWS.ENABLED",
                    "TOOLS.MCP.NEWS.BLOCK_PRIVATE_NETWORK_EGRESS",
                ),
            )
        )
    if webui_enabled and not config.get_bool(
        "SERVER.WEBUI.WALLPAPER_DOWNLOAD.BLOCK_PRIVATE_NETWORKS"
    ):
        issues.append(
            SecurityHardeningIssue(
                issue_id="webui_wallpaper_private_network_access_allowed",
                message=(
                    "WebUI wallpaper downloads can access private network destinations. Enable "
                    "private-network blocking to reduce SSRF risk."
                ),
                config_keys=(
                    "SERVER.WEBUI.ENABLED",
                    "SERVER.WEBUI.WALLPAPER_DOWNLOAD.BLOCK_PRIVATE_NETWORKS",
                ),
            )
        )
    if webui_enabled and not config.get_bool("SERVER.WEBUI.MEDIA_PREVIEWS.BLOCK_PRIVATE_NETWORKS"):
        issues.append(
            SecurityHardeningIssue(
                issue_id="webui_media_preview_private_network_access_allowed",
                message=(
                    "WebUI media previews can access private network destinations. Enable "
                    "private-network blocking to reduce SSRF risk."
                ),
                config_keys=(
                    "SERVER.WEBUI.ENABLED",
                    "SERVER.WEBUI.MEDIA_PREVIEWS.BLOCK_PRIVATE_NETWORKS",
                ),
            )
        )
    if config.get_bool("PLUGINS.FEATURES.DOWNLOADS") and config.get_bool(
        "PLUGINS.SECURITY.ALLOW_INSECURE_DOWNLOADS"
    ):
        issues.append(
            SecurityHardeningIssue(
                issue_id="plugin_insecure_downloads_allowed",
                message=(
                    "Plugin downloads permit insecure HTTP transport. Require verified HTTPS "
                    "downloads to prevent package interception."
                ),
                config_keys=(
                    "PLUGINS.FEATURES.DOWNLOADS",
                    "PLUGINS.SECURITY.ALLOW_INSECURE_DOWNLOADS",
                ),
            )
        )
    if not config.get_bool("PLUGINS.SECURITY.SAFETY_VALIDATION"):
        issues.append(
            SecurityHardeningIssue(
                issue_id="plugin_safety_validation_disabled",
                message=(
                    "Plugin safety validation is disabled. Re-enable the existing validator "
                    "before loading third-party plugins."
                ),
                config_keys=("PLUGINS.SECURITY.SAFETY_VALIDATION",),
            )
        )
    if network_exposed and not config.get_bool("OBSERVABILITY.LOGGING.ENABLED"):
        issues.append(
            SecurityHardeningIssue(
                issue_id="security_logging_disabled",
                message=(
                    "Central logging and audit ownership are disabled on a network-exposed "
                    "deployment, reducing incident detection and investigation capability."
                ),
                config_keys=("OBSERVABILITY.LOGGING.ENABLED",),
            )
        )
    return tuple(issues)
