"""SoAI - Default config schema: event bus [backend/core/config/default_schema/event_bus.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_event_bus_defaults",)


def build_event_bus_defaults() -> ConfigDict:
    return {
        "EVENT_BUS": {
            "QUEUE_SIZE": 10000,
            "NUM_WORKERS": 8,
            "PUBLISH_TIMEOUT_SEC": 0.25,
            "BACKPRESSURE_WARNING_DEPTH": False,
            "DISPATCH_TIMEOUT_SEC": 30.0,
            "PER_CALLBACK_TIMEOUT_SEC": 5.0,
            "SHUTDOWN_TIMEOUT_SEC": 10.0,
            "DOMAIN": {
                "OUTBOX": {
                    "POLL_INTERVAL_SEC": 0.25,
                    "BATCH_LIMIT": 100,
                    "PROCESSING_TIMEOUT_SEC": 10.0,
                    "QUARANTINE_DELAY_SEC": 86400,
                    "SUPERVISOR_RESTART_INITIAL_SEC": 0.5,
                    "SUPERVISOR_RESTART_MAX_SEC": 30.0,
                    "SUPERVISOR_RESTART_JITTER_SEC": 0.5,
                },
                "DELIVERY": {
                    "DEFAULT_TIMEOUT_SEC": 0.0,
                    "PER_CALLBACK_TIMEOUT_SEC": 30.0,
                },
            },
        },
    }
