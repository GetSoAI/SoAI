"""SoAI - Complete shared exception initialization keyword grammar [backend/core/errors/error_initialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("build_error_init_kwargs",)


class _ErrorInitKwargs(TypedDict):
    details: Mapping[str, JSONValue] | None
    operation: str | None
    cause: BaseException | None
    trace_id: str | None
    headers: Mapping[str, str] | None


def build_error_init_kwargs(
    details: Mapping[str, JSONValue] | None,
    operation: str | None,
    cause: BaseException | None,
    trace_id: str | None,
    headers: Mapping[str, str] | None,
) -> _ErrorInitKwargs:
    return {
        "details": details,
        "operation": operation,
        "cause": cause,
        "trace_id": trace_id,
        "headers": headers,
    }
