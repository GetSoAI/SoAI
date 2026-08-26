"""SoAI - Software update check result logging [backend/app/updater/software_update/check_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.protocols import LoggerProtocol
from core.types.json import JSONDict
from core.validation.boolean_coercion import coerce_bool_with_default

__all__ = ("log_software_update_check_result",)


def log_software_update_check_result(
    *,
    logger: LoggerProtocol,
    local_version: str,
    update_status: JSONDict,
    latest_release: JSONDict,
) -> None:
    latest_version = update_status.get("latest_version")
    latest_version_str = latest_version if isinstance(latest_version, str) else ""
    logger.info(
        "Your current version: v%s\nLatest version available: v%s",
        local_version,
        latest_version_str,
    )
    if not coerce_bool_with_default(
        update_status.get("update_available"),
        default=False,
        strict=False,
    ):
        logger.info("\nStatus: You are running the latest version!")
        return
    published_at_raw = latest_release.get("published_at", "N/A")
    published_at = published_at_raw.split("T")[0] if isinstance(published_at_raw, str) else "N/A"
    logger.info(
        "\nStatus: An update is available (v%s, published on %s).",
        latest_version_str,
        published_at,
    )
    logger.info(
        "More info: %s\nInstall the update from the SoAI Web UI.",
        latest_release.get("html_url", "N/A"),
    )
