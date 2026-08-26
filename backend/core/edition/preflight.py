"""SoAI - Core edition startup preflight [backend/core/edition/preflight.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import EditionUnavailableError

__all__ = ("require_core_edition_request",)

_REMOVED_OS_ARGUMENTS = frozenset(
    (
        "--soai-os",
        "--soai_os",
        "-soai-os",
        "-soai_os",
    )
)
_REMOVED_OS_ENVIRONMENT_FLAGS = (
    "SOAI_OS_ENABLED",
    "SOAI_OS_INSTALLER",
)


def require_core_edition_request(arguments: list[str]) -> None:
    requested_arguments = tuple(
        argument for argument in arguments if argument in _REMOVED_OS_ARGUMENTS
    )
    requested_environment = tuple(
        name for name in _REMOVED_OS_ENVIRONMENT_FLAGS if os.environ.get(name, "").strip() == "1"
    )
    if not requested_arguments and not requested_environment:
        return
    raise EditionUnavailableError(
        "SoAI OS is unavailable from the Core entrypoint; run the explicit SoAI OS entrypoint from a SoAI OS artifact.",
        details={
            "arguments": list(requested_arguments),
            "environment": list(requested_environment),
        },
        operation="edition.core.preflight",
    )
