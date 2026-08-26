"""SoAI - Streaming dependency bundle construction [backend/features/api/streaming/stream_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.api.streaming.internal_protocols import StreamDependenciesSourceProtocol
from features.api.streaming.stream_dependencies_validation import (
    require_stream_dependencies_typed_config_accessors,
)
from features.api.streaming.types import StreamDependencies

__all__ = ("build_stream_dependencies",)


def build_stream_dependencies(
    api_dependencies: StreamDependenciesSourceProtocol,
) -> StreamDependencies:
    registry = api_dependencies.stream_channel_registry
    deps = StreamDependencies(
        config=api_dependencies.config,
        task_registry=api_dependencies.task_registry,
        cancellation_coordinator=api_dependencies.cancellation_coordinator,
        cancellation_history=api_dependencies.cancellation_history,
        event_bus=api_dependencies.event_bus,
        shutdown_event=api_dependencies.shutdown_event,
        stream_channel_registry=registry,
        cancellation_binder=api_dependencies.task_cancellation_binder,
        finalizer_tracker=api_dependencies.task_finalizer_tracker,
        prompt_token_counter=api_dependencies.prompt_token_counter,
        metrics_manager=api_dependencies.metrics_manager,
    )
    require_stream_dependencies_typed_config_accessors(deps)
    return deps
