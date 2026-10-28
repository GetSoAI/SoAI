"""SoAI - Accepted configuration to API connection transition projection [backend/app/connection_transition_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.config.dotted_key_access import get_nested_config_value
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.network.hosts import normalize_host
from core.oauth.management_urls import resolve_oauth_public_origin
from core.runtime.connection_transition import ConnectionTransition
from core.runtime.state_access import read_state_flag
from core.types.json_value import copy_json_dict
from core.validation.booleans import parse_bool, parse_bool_flag_with_default
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.runtime.api_endpoint import RuntimeApiEndpoint
    from core.runtime.connection_transition import (
        ConnectionTransitionDestination,
        ConnectionTransitionScheme,
    )
    from core.runtime.protocols import RuntimeStateStoreProtocol
    from core.types.json import JSONDict

__all__ = (
    "project_connection_transition",
    "record_accepted_connection_transition",
)

_PROJECTION_FAILURES = (ValidationError,) + RECOVERABLE_EXCEPTIONS

OPERATION_RECORD_CONNECTION_TRANSITION = "application_runtime.record_connection_transition"


def project_connection_transition(
    *,
    configuration_revision: int,
    instance_id: str,
    config_dict: JSONDict,
    endpoint: RuntimeApiEndpoint,
    active_proxy_headers_enabled: bool,
) -> ConnectionTransition:
    public_origin = _resolve_requested_public_origin(config_dict)
    destination: ConnectionTransitionDestination
    if public_origin is not None:
        destination = "public_origin"
    elif _requires_manual_address(config_dict, endpoint, active_proxy_headers_enabled):
        destination = "manual"
    else:
        destination = "same_address"
    return ConnectionTransition(
        configuration_revision=configuration_revision,
        instance_id=instance_id,
        current_scheme=_current_scheme(endpoint),
        requested_scheme=_requested_scheme(config_dict),
        destination=destination,
        public_origin=public_origin,
    )


async def record_accepted_connection_transition(
    *,
    runtime_state: RuntimeStateStoreProtocol,
    resolve_instance_id: Callable[[], Awaitable[str]] | None,
    configuration_revision: int,
    config_dict: JSONDict,
    logger: LoggerProtocol,
) -> None:
    if resolve_instance_id is None:
        return
    restart_state_manager = runtime_state.restart_state_manager
    endpoint = runtime_state.runtime_api_endpoint
    if restart_state_manager is None or endpoint is None:
        return
    accepted_config = copy_json_dict(config_dict)
    fastapi_app = runtime_state.fastapi_app
    active_proxy_headers_enabled = fastapi_app is not None and read_state_flag(
        fastapi_app.state, "proxy_headers_enabled"
    )
    try:
        transition = project_connection_transition(
            configuration_revision=configuration_revision,
            instance_id=await resolve_instance_id(),
            config_dict=accepted_config,
            endpoint=endpoint,
            active_proxy_headers_enabled=active_proxy_headers_enabled,
        )
    except _PROJECTION_FAILURES as exception:
        log_exception(
            logger,
            exception,
            message="Connection transition address is unavailable; recording manual guidance.",
            operation=OPERATION_RECORD_CONNECTION_TRANSITION,
            details={"revision": configuration_revision},
            level="warning",
        )
        await restart_state_manager.record_unavailable_connection_transition(
            configuration_revision=configuration_revision,
            current_scheme=_current_scheme(endpoint),
            requested_scheme=_requested_scheme(accepted_config),
        )
        return
    await restart_state_manager.record_connection_transition(transition)


def _current_scheme(endpoint: RuntimeApiEndpoint) -> ConnectionTransitionScheme:
    return "https" if endpoint.scheme == "https" else "http"


def _requested_scheme(config_dict: JSONDict) -> ConnectionTransitionScheme:
    tls_enabled = parse_bool_flag_with_default(
        get_nested_config_value(config_dict, "SERVER.HTTP.SSL.TLS_ENABLED"),
        default=False,
    )
    return "https" if tls_enabled else "http"


def _resolve_requested_public_origin(config_dict: JSONDict) -> str | None:
    configured = get_nested_config_value(config_dict, "SERVER.PUBLIC_ORIGIN")
    if not isinstance(configured, str) or not configured.strip():
        return None
    try:
        return resolve_oauth_public_origin(configured)
    except ValidationError:
        return None


def _requires_manual_address(
    config_dict: JSONDict,
    endpoint: RuntimeApiEndpoint,
    active_proxy_headers_enabled: bool,
) -> bool:
    configured_public_origin = get_nested_config_value(config_dict, "SERVER.PUBLIC_ORIGIN")
    if isinstance(configured_public_origin, str) and configured_public_origin.strip():
        return True
    requested_proxy_headers = parse_bool(
        get_nested_config_value(config_dict, "SERVER.HTTP.PROXY.ENABLE_HEADERS"),
        False,
    )
    if active_proxy_headers_enabled or requested_proxy_headers or endpoint.fallback_active:
        return True
    requested_host = get_nested_config_value(config_dict, "SERVER.HTTP.NETWORK.HOST")
    requested_port = get_nested_config_value(config_dict, "SERVER.HTTP.NETWORK.PORT")
    if not isinstance(requested_host, str) or not is_strict_int(requested_port):
        return True
    return (
        normalize_host(requested_host) != normalize_host(endpoint.bind_host)
        or requested_port != endpoint.preferred_port
    )
