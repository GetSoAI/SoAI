"""SoAI - Streaming dependency validation [backend/features/api/streaming/stream_dependencies_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from features.api.streaming.types import StreamDependencies

__all__ = ("require_stream_dependencies_typed_config_accessors",)


def require_stream_dependencies_typed_config_accessors(deps: StreamDependencies) -> None:
    config = deps.config
    try:
        get_value = config.get
    except AttributeError:
        get_value = None
    if not callable(get_value):
        raise ValidationError(
            "StreamDependencies.config must provide typed config accessors.",
            details={"missing": "get", "actual_type": type(config).__name__},
        )
    try:
        get_int_value = config.get_int
    except AttributeError:
        get_int_value = None
    if not callable(get_int_value):
        raise ValidationError(
            "StreamDependencies.config must provide typed config accessors.",
            details={"missing": "get_int", "actual_type": type(config).__name__},
        )
    try:
        get_float_value = config.get_float
    except AttributeError:
        get_float_value = None
    if not callable(get_float_value):
        raise ValidationError(
            "StreamDependencies.config must provide typed config accessors.",
            details={"missing": "get_float", "actual_type": type(config).__name__},
        )
    try:
        get_bool_value = config.get_bool
    except AttributeError:
        get_bool_value = None
    if not callable(get_bool_value):
        raise ValidationError(
            "StreamDependencies.config must provide typed config accessors.",
            details={"missing": "get_bool", "actual_type": type(config).__name__},
        )
    try:
        get_str_value = config.get_str
    except AttributeError:
        get_str_value = None
    if not callable(get_str_value):
        raise ValidationError(
            "StreamDependencies.config must provide typed config accessors.",
            details={"missing": "get_str", "actual_type": type(config).__name__},
        )
