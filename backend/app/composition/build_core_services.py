"""SoAI - Core application infrastructure service construction [backend/app/composition/build_core_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import dataclasses

import httpx2

from app.application_dependencies import ApplicationLogging
from app.banner_system import resolve_banner_system
from app.lifecycle.signals import register_banner_defaults
from core.config.numeric import coerce_float_or_none, coerce_positive_int
from core.config.numeric_lenient import (
    coerce_lenient_positive_int,
    coerce_timeout_seconds,
)
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ConfigurationError, ValidationError
from core.events.bus import EventBus
from core.events.durable_delivery import DurableEventDelivery
from core.logging.colors import LOG_BANNER_DEFAULTS
from core.logging.manager import LoggingManager
from core.logging.protocols import LoggerProtocol
from core.runtime.network_http_client import create_guarded_async_http_client
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.timing.constants import (
    BACKGROUND_TIMEOUT_SEC,
    INTERACTIVE_TIMEOUT_SEC,
    LOCAL_IO_TIMEOUT_SEC,
    LONG_REQUEST_TIMEOUT_SEC,
)

__all__ = (
    "build_domain_event_delivery",
    "build_event_bus",
    "build_http_client",
    "ensure_banner_system",
)


def ensure_banner_system(
    *,
    logging_instance: ApplicationLogging,
    log_manager: LoggingManager,
    banner_width: int,
) -> ApplicationLogging:
    banner_system = resolve_banner_system(
        logger=logging_instance.logger,
        banner_width=banner_width,
        current_banner_system=logging_instance.banner_system,
        logging_manager=log_manager,
        banner_system_factory=log_manager.get_banner_system,
        register_defaults=lambda system: register_banner_defaults(
            system,
            list(LOG_BANNER_DEFAULTS),
        ),
    )
    return dataclasses.replace(logging_instance, banner_system=banner_system)


def build_event_bus(
    *,
    config: ConfigProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    lifecycle_logger: LoggerProtocol,
) -> EventBus:
    queue_size_value = coerce_positive_int(
        config.get("SYSTEM.EVENT_BUS.QUEUE_SIZE", 10000),
        default=10000,
        minimum=1,
        label="SYSTEM.EVENT_BUS.QUEUE_SIZE",
        logger=lifecycle_logger,
    )
    worker_count_value = coerce_positive_int(
        config.get("SYSTEM.EVENT_BUS.NUM_WORKERS", 8),
        default=8,
        minimum=1,
        label="SYSTEM.EVENT_BUS.NUM_WORKERS",
        logger=lifecycle_logger,
    )
    publish_timeout_value = coerce_float_or_none(
        config.get("SYSTEM.EVENT_BUS.PUBLISH_TIMEOUT_SEC", 1.0),
    )
    if queue_size_value and (publish_timeout_value is None or publish_timeout_value <= 0):
        raise ValidationError(
            "SYSTEM.EVENT_BUS.PUBLISH_TIMEOUT_SEC must be a positive number when SYSTEM.EVENT_BUS.QUEUE_SIZE is finite.",
            details={
                "SYSTEM.EVENT_BUS.QUEUE_SIZE": queue_size_value,
                "SYSTEM.EVENT_BUS.PUBLISH_TIMEOUT_SEC": publish_timeout_value,
            },
        )
    backpressure_depth_value = config.get("SYSTEM.EVENT_BUS.BACKPRESSURE_WARNING_DEPTH")
    backpressure_depth = None
    if backpressure_depth_value is not None:
        depth_candidate = None
        if isinstance(backpressure_depth_value, bool):
            depth_candidate = None
        elif isinstance(backpressure_depth_value, int | float):
            depth_candidate = int(backpressure_depth_value)
        elif isinstance(backpressure_depth_value, str):
            stripped = backpressure_depth_value.strip()
            if stripped:
                try:
                    depth_candidate = int(stripped)
                except ValueError:
                    depth_candidate = None
        if depth_candidate and depth_candidate > 0:
            backpressure_depth = depth_candidate
    dispatch_timeout_value = coerce_float_or_none(
        config.get("SYSTEM.EVENT_BUS.DISPATCH_TIMEOUT_SEC", INTERACTIVE_TIMEOUT_SEC),
    )
    if dispatch_timeout_value is None or dispatch_timeout_value <= 0:
        raise ValidationError(
            "SYSTEM.EVENT_BUS.DISPATCH_TIMEOUT_SEC must be a positive number.",
            details={"SYSTEM.EVENT_BUS.DISPATCH_TIMEOUT_SEC": dispatch_timeout_value},
        )
    shutdown_timeout_value = coerce_float_or_none(
        config.get("SYSTEM.EVENT_BUS.SHUTDOWN_TIMEOUT_SEC"),
    )
    if shutdown_timeout_value is not None and shutdown_timeout_value <= 0:
        shutdown_timeout_value = None
    per_callback_timeout_value = coerce_float_or_none(
        config.get(
            "SYSTEM.EVENT_BUS.PER_CALLBACK_TIMEOUT_SEC",
            LOCAL_IO_TIMEOUT_SEC,
        ),
    )
    if per_callback_timeout_value is None or per_callback_timeout_value <= 0:
        raise ValidationError(
            "SYSTEM.EVENT_BUS.PER_CALLBACK_TIMEOUT_SEC must be a positive number.",
            details={"SYSTEM.EVENT_BUS.PER_CALLBACK_TIMEOUT_SEC": per_callback_timeout_value},
        )
    return EventBus(
        queue_size=queue_size_value,
        num_workers=worker_count_value,
        metrics_recorder=None,
        publish_timeout_sec=publish_timeout_value,
        backpressure_warning_depth=backpressure_depth,
        dispatch_timeout_sec=dispatch_timeout_value,
        shutdown_timeout_sec=shutdown_timeout_value,
        per_callback_timeout_sec=per_callback_timeout_value,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
    )


def build_domain_event_delivery(*, config: ConfigProtocol) -> DurableEventDelivery:
    per_callback_timeout_value = coerce_timeout_seconds(
        config.get(
            "SYSTEM.EVENT_BUS.DOMAIN.DELIVERY.PER_CALLBACK_TIMEOUT_SEC",
            INTERACTIVE_TIMEOUT_SEC,
        ),
        default=INTERACTIVE_TIMEOUT_SEC,
    )
    per_callback_timeout_sec = (
        None if per_callback_timeout_value <= 0.0 else float(per_callback_timeout_value)
    )
    default_timeout_value = coerce_timeout_seconds(
        config.get("SYSTEM.EVENT_BUS.DOMAIN.DELIVERY.DEFAULT_TIMEOUT_SEC", 0.0),
        default=0.0,
    )
    default_timeout_sec = None if default_timeout_value <= 0.0 else float(default_timeout_value)
    return DurableEventDelivery(
        per_callback_timeout_sec=per_callback_timeout_sec,
        default_timeout_sec=default_timeout_sec,
    )


_DEFAULT_MAX_CONNECTIONS = 200
_DEFAULT_MAX_KEEPALIVE_CONNECTIONS = 50


def build_http_client(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
) -> httpx2.AsyncClient:
    http_limits_config = config.get("MODELS.ROUTING.HTTP_CLIENT_LIMITS", {})
    if http_limits_config is None:
        http_limits_config = {}
    if not isinstance(http_limits_config, dict):
        raise ConfigurationError("MODELS.ROUTING.HTTP_CLIENT_LIMITS must be a mapping.")
    max_connections = coerce_lenient_positive_int(
        http_limits_config.get("MAX_CONNECTIONS", _DEFAULT_MAX_CONNECTIONS),
        default=_DEFAULT_MAX_CONNECTIONS,
    )
    max_keepalive_connections = coerce_lenient_positive_int(
        http_limits_config.get("MAX_KEEPALIVE_CONNECTIONS", _DEFAULT_MAX_KEEPALIVE_CONNECTIONS),
        default=_DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
    )
    limits = httpx2.Limits(
        max_connections=max_connections,
        max_keepalive_connections=max_keepalive_connections,
    )
    http_timeout_config = config.get("MODELS.ROUTING.HTTP_CLIENT_TIMEOUTS", {})
    if http_timeout_config is None:
        http_timeout_config = {}
    if not isinstance(http_timeout_config, dict):
        raise ConfigurationError("MODELS.ROUTING.HTTP_CLIENT_TIMEOUTS must be a mapping.")
    timeout = httpx2.Timeout(
        connect=coerce_timeout_seconds(
            http_timeout_config.get("CONNECT", INTERACTIVE_TIMEOUT_SEC),
            default=INTERACTIVE_TIMEOUT_SEC,
        ),
        read=coerce_timeout_seconds(
            http_timeout_config.get("READ", LONG_REQUEST_TIMEOUT_SEC),
            default=LONG_REQUEST_TIMEOUT_SEC,
        ),
        write=coerce_timeout_seconds(
            http_timeout_config.get("WRITE", BACKGROUND_TIMEOUT_SEC),
            default=BACKGROUND_TIMEOUT_SEC,
        ),
        pool=coerce_timeout_seconds(
            http_timeout_config.get("POOL", INTERACTIVE_TIMEOUT_SEC),
            default=INTERACTIVE_TIMEOUT_SEC,
        ),
    )

    trust_env_config = config.get("MODELS.ROUTING.HTTP_CLIENT_TRUST_ENV", False)
    if not isinstance(trust_env_config, bool):
        raise ConfigurationError("MODELS.ROUTING.HTTP_CLIENT_TRUST_ENV must be a boolean.")
    return create_guarded_async_http_client(
        runtime_flags,
        source="core_http_client",
        timeout=timeout,
        limits=limits,
        trust_env=trust_env_config,
    )
