"""SoAI - Shared banner system initialization [backend/app/banner_system.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.logging.protocols import (
        LogBannerSystemProtocol,
        LoggerProtocol,
        LoggingManagerProtocol,
    )

    type BannerSystemFactory = Callable[[LoggerProtocol, int], LogBannerSystemProtocol]
    type RegisterBannerDefaults = Callable[[LogBannerSystemProtocol], None]

__all__ = ("resolve_banner_system",)


def resolve_banner_system(
    *,
    logger: LoggerProtocol,
    banner_width: int,
    current_banner_system: LogBannerSystemProtocol | None,
    logging_manager: LoggingManagerProtocol | None,
    banner_system_factory: BannerSystemFactory,
    register_defaults: RegisterBannerDefaults,
) -> LogBannerSystemProtocol:
    banner_system = current_banner_system
    if logging_manager is not None:
        managed_system = logging_manager.get_banner_system(logger, banner_width)
        if banner_system is not managed_system:
            banner_system = managed_system
    elif banner_system is None:
        banner_system = banner_system_factory(logger, banner_width)
    if banner_system is None:
        raise StateError("Banner system could not be initialized.")
    register_defaults(banner_system)
    return banner_system
