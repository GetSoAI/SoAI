"""SoAI - Typed Starlette state access without exception-driven attribute probing [backend/core/runtime/state_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from starlette.datastructures import State

from core.runtime.protocols import RequestProtocol

__all__ = (
    "read_request_state_flag",
    "read_request_state_value",
    "read_state_flag",
    "read_state_has_key",
    "read_state_value",
)


def read_state_has_key(state: State, key: str) -> bool:
    return key in state


def read_state_value[ValueT](state: State, key: str, value_type: type[ValueT]) -> ValueT | None:
    if key not in state:
        return None
    value = state[key]
    if isinstance(value, value_type):
        return value
    return None


def read_state_flag(state: State, key: str, *, default: bool = False) -> bool:
    if key not in state:
        return default
    value = state[key]
    if value is None:
        return default
    return bool(value)


def read_request_state_value[ValueT](
    request: RequestProtocol,
    key: str,
    value_type: type[ValueT],
) -> ValueT | None:
    state = request.state
    if not isinstance(state, State):
        return None
    return read_state_value(state, key, value_type)


def read_request_state_flag(
    request: RequestProtocol,
    key: str,
    *,
    default: bool = False,
) -> bool:
    state = request.state
    if not isinstance(state, State):
        return default
    return read_state_flag(state, key, default=default)
