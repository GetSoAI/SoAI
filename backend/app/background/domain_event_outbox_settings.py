"""SoAI - Domain event outbox dispatcher settings loader [backend/app/background/domain_event_outbox_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.clamped_numeric import read_min_clamped_float, read_min_clamped_int
from core.config.protocols import ConfigProtocol

__all__ = (
    "DomainEventOutboxDispatcherSettings",
    "load_domain_event_outbox_dispatcher_settings",
    "load_domain_event_outbox_quarantine_delay_ms",
)


@dataclass(frozen=True, slots=True)
class DomainEventOutboxDispatcherSettings:
    poll_interval_sec: float
    batch_limit: int
    processing_timeout_ms: int
    supervisor_restart_initial_sec: float
    supervisor_restart_max_sec: float
    supervisor_restart_jitter_sec: float


def load_domain_event_outbox_quarantine_delay_ms(config: ConfigProtocol) -> int:
    delay_sec = read_min_clamped_float(
        config,
        "SYSTEM.EVENT_BUS.DOMAIN.OUTBOX.QUARANTINE_DELAY_SEC",
        86400.0,
        minimum=0.0,
    )
    return int(delay_sec * 1000.0)


def load_domain_event_outbox_dispatcher_settings(
    config: ConfigProtocol,
) -> DomainEventOutboxDispatcherSettings:
    poll_interval_sec = read_min_clamped_float(
        config,
        "SYSTEM.EVENT_BUS.DOMAIN.OUTBOX.POLL_INTERVAL_SEC",
        0.25,
        minimum=0.1,
    )
    batch_limit = read_min_clamped_int(
        config,
        "SYSTEM.EVENT_BUS.DOMAIN.OUTBOX.BATCH_LIMIT",
        100,
        minimum=1,
    )
    processing_timeout_sec = read_min_clamped_float(
        config,
        "SYSTEM.EVENT_BUS.DOMAIN.OUTBOX.PROCESSING_TIMEOUT_SEC",
        10.0,
        minimum=0.001,
    )
    supervisor_initial_sec = read_min_clamped_float(
        config,
        "SYSTEM.EVENT_BUS.DOMAIN.OUTBOX.SUPERVISOR_RESTART_INITIAL_SEC",
        0.5,
        minimum=0.0,
    )
    supervisor_max_sec = read_min_clamped_float(
        config,
        "SYSTEM.EVENT_BUS.DOMAIN.OUTBOX.SUPERVISOR_RESTART_MAX_SEC",
        30.0,
        minimum=0.0,
    )
    supervisor_jitter_sec = read_min_clamped_float(
        config,
        "SYSTEM.EVENT_BUS.DOMAIN.OUTBOX.SUPERVISOR_RESTART_JITTER_SEC",
        0.5,
        minimum=0.0,
    )
    supervisor_max_sec = max(float(supervisor_initial_sec), float(supervisor_max_sec))
    return DomainEventOutboxDispatcherSettings(
        poll_interval_sec=float(poll_interval_sec),
        batch_limit=int(batch_limit),
        processing_timeout_ms=int(processing_timeout_sec * 1000.0),
        supervisor_restart_initial_sec=float(supervisor_initial_sec),
        supervisor_restart_max_sec=float(supervisor_max_sec),
        supervisor_restart_jitter_sec=float(supervisor_jitter_sec),
    )
