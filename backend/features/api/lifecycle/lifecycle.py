"""SoAI - API lifecycle orchestrator for FastAPI application initialization [backend/features/api/lifecycle/lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.rate_limiting.moving_window import MovingWindowRateLimiter
from features.api.api_cors_runtime import (
    build_cors_runtime_config,
    cors_runtime_config_to_json,
)
from features.api.internal_protocols import ApiRouteLoaderServiceProtocol
from features.api.lifecycle.app_state_manager import (
    apply_cors_state_to_app,
    apply_security_state_to_app,
    update_security_runtime_state,
)
from features.api.lifecycle.cors_state import configure_cors_state
from features.api.lifecycle.exception_handlers import register_exception_handlers
from features.api.lifecycle.middleware_registry import (
    register_middleware_stack,
    update_middleware_options,
)
from features.api.lifecycle.rate_limiting_config import (
    apply_rate_limiting,
    build_rate_limit_configuration,
)
from features.api.lifecycle.router_setup import (
    configure_registered_route_dependencies,
    configure_router_dependencies,
)
from features.api.lifecycle.security_state import configure_security_state
from features.api.middleware.security.anomaly_tracker import reset_anomaly_alert
from features.api.middleware.security_headers import SecurityHeadersMiddleware
from features.api.rate_limiting.rate_limit_dependency import rate_limit_dependency
from features.api.request_body_policy import build_request_body_policy
from features.api.runtime.container.api_routers import (
    ApiRouters,
    build_api_routers,
    iter_app_routers,
)
from features.api.runtime.container.container import build_api_dependencies
from features.api.runtime.container.route_composition import ApiRouteComposition
from features.api.runtime.context import attach_api_dependencies
from features.api.static_assets import configure_webui_static_assets

if TYPE_CHECKING:
    from features.api.runtime.container.internal_protocols import (
        ApiRuntimeServicesBuilderProtocol,
        MainAppInstanceProtocol,
    )

__all__ = (
    "ApiLifecycleManager",
    "ApiLifecycleManagerDependencies",
)

LOGGER_NAME = "SoAI.features.api.lifecycle"


@dataclass(frozen=True, slots=True)
class ApiLifecycleManagerDependencies:
    fastapi_app: FastAPI
    request_rate_limiter: MovingWindowRateLimiter
    route_loader_service: ApiRouteLoaderServiceProtocol
    build_api_runtime_services: ApiRuntimeServicesBuilderProtocol
    api_route_composition: ApiRouteComposition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApiLifecycleManagerDependencies",
            build_api_runtime_services=self.build_api_runtime_services,
            fastapi_app=self.fastapi_app,
            request_rate_limiter=self.request_rate_limiter,
            route_loader_service=self.route_loader_service,
            api_route_composition=self.api_route_composition,
        )


class ApiLifecycleManager:
    def __init__(self, deps: ApiLifecycleManagerDependencies) -> None:
        self.app = deps.fastapi_app
        self.request_rate_limiter = deps.request_rate_limiter
        self.route_loader_service = deps.route_loader_service
        self.build_api_runtime_services = deps.build_api_runtime_services
        self.api_route_composition = deps.api_route_composition

    def initialize(self, main_app_instance: MainAppInstanceProtocol) -> FastAPI:
        try:
            _ = main_app_instance.services
            security = main_app_instance.security
            metadata = main_app_instance.metadata
        except AttributeError as exception:
            raise ValidationError(
                "main_app_instance is missing services, security, or metadata.",
            ) from exception
        if not security.primary_signing_secret or not security.verification_secrets:
            raise ValidationError("main_app_instance is missing required security configuration.")
        app = self.app
        request_rate_limiter = self.request_rate_limiter
        try:
            already_initialized = bool(app.state.initialized)
        except AttributeError:
            already_initialized = False
        if not already_initialized:
            register_exception_handlers(app)
        if not self.route_loader_service.is_loaded:
            routers = build_api_routers(
                self.api_route_composition.host_management_router_factory,
            )
            configure_router_dependencies(routers)
            self.route_loader_service.load_routes(routers)
            configure_registered_route_dependencies(routers)
            app.state.api_routers = routers
        api_dependencies = build_api_dependencies(
            main_app_instance,
            build_api_runtime_services=self.build_api_runtime_services,
        )
        attach_api_dependencies(app, api_dependencies)
        was_quiescent = True
        if already_initialized:
            was_quiescent = bool(api_dependencies.orchestrator_control.is_quiescent())
            if not was_quiescent:
                api_dependencies.orchestrator_control.set_quiescent(True)
        try:
            config_obj = api_dependencies.config
            api_dependencies.auth_config.configure(
                primary_signing_secret=security.primary_signing_secret,
                verification_secrets=security.verification_secrets,
            )
            app.version = metadata.version
            reset_anomaly_alert(api_dependencies.proxy_header_anomaly_tracker)
            rate_limit_config = build_rate_limit_configuration(config_obj)
            apply_rate_limiting(app, request_rate_limiter, rate_limit_config, already_initialized)
            try:
                existing_security_headers_state_raw = app.state.security_headers_state
            except AttributeError:
                existing_security_headers_state_raw = None
            existing_security_headers_state: SecurityHeadersMiddleware.ConfigState | None = (
                existing_security_headers_state_raw
                if isinstance(
                    existing_security_headers_state_raw,
                    SecurityHeadersMiddleware.ConfigState,
                )
                else None
            )
            security_config = configure_security_state(config_obj, existing_security_headers_state)
            apply_security_state_to_app(app, security_config)
            update_security_runtime_state(
                api_dependencies.security_runtime_state,
                proxy_headers_enabled=security_config.proxy_headers_enabled,
                trusted_proxy_networks=security_config.trusted_proxy_networks,
                https_redirect_active=security_config.force_https_redirect,
                hsts_enabled=security_config.hsts_enabled,
                content_security_policy=security_config.content_security_policy,
                content_security_policy_insecure=security_config.content_security_policy_insecure,
            )
            cors_config = build_cors_runtime_config(
                config_obj,
                log_wildcard_warning=False,
            )
            cors_state = configure_cors_state(cors_config)
            apply_cors_state_to_app(app, cors_state)
            if not already_initialized:
                request_body_policy = build_request_body_policy(config_obj)
                register_middleware_stack(
                    app,
                    cors_config,
                    security_config.security_headers_state,
                    security_config.force_https_redirect,
                    request_body_policy,
                )
            else:
                cors_options = cors_runtime_config_to_json(cors_config)
                if update_middleware_options(app, CORSMiddleware, cors_options):
                    app.middleware_stack = app.build_middleware_stack()
            if already_initialized:
                get_logger(LOGGER_NAME).info(
                    "API already initialized; refreshing runtime configuration.",
                )
            else:
                try:
                    routers_obj = app.state.api_routers
                except AttributeError:
                    routers_obj = None
                if isinstance(routers_obj, ApiRouters):
                    routers = routers_obj
                else:
                    routers = build_api_routers(
                        self.api_route_composition.host_management_router_factory,
                    )
                    app.state.api_routers = routers
                configure_router_dependencies(routers)
                configure_registered_route_dependencies(routers)
                rate_limit_dep = Depends(rate_limit_dependency)
                for router in iter_app_routers(routers):
                    app.include_router(router, dependencies=[rate_limit_dep])
            configure_webui_static_assets(app, config_obj)
            app.state.initialized = True
            return app
        finally:
            if already_initialized and (not was_quiescent):
                api_dependencies.orchestrator_control.set_quiescent(False)
