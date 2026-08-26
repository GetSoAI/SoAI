"""SoAI - Third party logging setup [backend/core/logging/third_party_setup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging

from core.logging.uvicorn_config import UvicornConnectionDemoteFilter

__all__ = ("setup_third_party_logging",)

_UVICORN_LOGGERS = frozenset({"uvicorn", "uvicorn.error"})


def setup_third_party_logging(
    *,
    root_logger: logging.Logger,
    managed_logger_names: list[str],
    third_party_log_levels: dict[str, int],
    root_level: int,
) -> None:
    connection_demote_filter = UvicornConnectionDemoteFilter()
    for logger_name in managed_logger_names:
        logger_instance = logging.getLogger(logger_name)
        logger_instance.propagate = False
        logger_instance.setLevel(third_party_log_levels.get(logger_name, root_level))
        logger_instance.handlers = list(root_logger.handlers)
        if logger_name in _UVICORN_LOGGERS:
            logger_instance.filters = [
                logger_filter
                for logger_filter in logger_instance.filters
                if not isinstance(logger_filter, UvicornConnectionDemoteFilter)
            ]
            logger_instance.addFilter(connection_demote_filter)
