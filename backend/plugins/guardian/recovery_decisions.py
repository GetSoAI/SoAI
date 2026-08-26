"""SoAI - Guardian recovery decision aggregation [backend/plugins/guardian/recovery_decisions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence

from core.errors.exception_logging import log_exception
from core.logging.protocols import LoggerProtocol

__all__ = ("collect_guardian_recovery_decisions",)

OPERATION_PLUGIN_GUARDIAN_GUARDIAN_HEALTH_CHECK_LOOP = "plugin_guardian.guardianhealth_check_loop"


def collect_guardian_recovery_decisions(
    *,
    check_names: Sequence[str],
    check_results: Sequence[dict[str, str] | BaseException],
    logger: LoggerProtocol,
) -> dict[str, str]:
    plugins_to_recover: dict[str, str] = {}
    for check_name, data in zip(check_names, check_results, strict=False):
        if isinstance(data, BaseException):
            log_exception(
                logger,
                data,
                message="Guardian check failed for current iteration",
                operation=OPERATION_PLUGIN_GUARDIAN_GUARDIAN_HEALTH_CHECK_LOOP,
                details={"check_name": check_name},
                level="warning",
            )
            continue
        for plugin_name, recovery_reason in data.items():
            if plugin_name not in plugins_to_recover:
                plugins_to_recover[plugin_name] = recovery_reason
    return plugins_to_recover
