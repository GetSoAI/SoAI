"""SoAI - Shared validation helpers for runtime checks [backend/core/validation/runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.types.json import JSONDict, JSONValue
from core.validation.boolean_coercion import coerce_success_flag

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "ensure_minimum_python_version",
    "is_success_payload",
)


def is_success_payload(
    payload: JSONDict | Mapping[str, JSONValue] | None,
    logger: LoggerProtocol,
    *,
    operation: str,
    recover_message: str | None = None,
    default: bool = False,
) -> bool:
    if not isinstance(payload, Mapping):
        return default
    return coerce_success_flag(
        payload,
        "success",
        logger=logger,
        operation=operation,
        default=default,
        recover_message=recover_message,
    )


def ensure_minimum_python_version(
    major: int = 3,
    minor: int = 13,
    *,
    component: str = "",
    exit_on_failure: bool = False,
    failure_message: str | None = None,
) -> None:
    current = (sys.version_info.major, sys.version_info.minor)
    if current < (major, minor):
        min_version = f"{major}.{minor}"
        current_version = (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
        if failure_message is None:
            failure_message = (
                f"SoAI requires Python {min_version} or later, but you are running Python {current_version}.\n"
                f"Please run SoAI with Python {min_version}+."
            )
        else:
            failure_message = failure_message.format(
                min_version=min_version,
                current_version=current_version,
            )
        if component:
            failure_message = f"{component}: {failure_message}"
        if exit_on_failure:
            sys.stderr.write(f"{failure_message}\n")
            sys.stderr.flush()
        raise StateError(failure_message)
