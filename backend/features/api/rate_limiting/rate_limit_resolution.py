"""SoAI - Rate limit configuration resolution for API routes [backend/features/api/rate_limiting/rate_limit_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi.routing import APIRoute, APIWebSocketRoute

from core.errors.exceptions import StateError, ValidationError
from core.rate_limiting.definitions import RateLimitRule
from core.rate_limiting.parsing import parse_rate_limit_rules
from core.serialization.json import serialize_json_compact_stable
from core.system_api.route_paths import (
    OPENAI_OPENAPI_SCHEMA_PATH,
    SOAI_API_OPENAPI_SCHEMA_PATH,
)
from core.validation.string_sequences import normalize_string_sequence
from features.api.rate_limiting.rate_limit_overrides import (
    RateLimitRouterOverride,
    normalize_rate_limit_router_overrides,
    normalize_rate_limit_value,
)
from features.api.runtime.container.api_routers import (
    ApiRouters,
    iter_rate_limit_router_sources,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "OPENAPI_SCHEMA_RATE_LIMIT_TARGET",
    "ResolvedPathLimit",
    "ResolvedRateLimitConfig",
    "RouterLimitTarget",
    "build_resolved_rate_limit_config",
    "build_router_limit_targets",
    "rate_limit_config_signature",
    "validate_rate_limit_config_keys",
)

OPENAPI_SCHEMA_RATE_LIMIT_TARGET = "openapi_schema"
RATE_LIMIT_CONFIG_KEYS: frozenset[str] = frozenset(
    {"ENABLED", "DEFAULT_LIMIT", "STREAM_LIMIT", "ROUTERS"},
)


@dataclass(frozen=True, slots=True)
class RouterLimitTarget:
    path_prefix: str
    default_stream_paths: tuple[str, ...]
    route_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResolvedPathLimit:
    limit_string: str
    rules: tuple[RateLimitRule, ...]


@dataclass(frozen=True, slots=True)
class ResolvedRateLimitConfig:
    enabled: bool
    signature: str
    path_limits: MappingProxyType[str, ResolvedPathLimit]


def _join_paths(prefix: str, path: str) -> str:
    if not prefix:
        return path if path.startswith("/") else f"/{path}"
    normalized_prefix = prefix.rstrip("/")
    if path == normalized_prefix or path.startswith(f"{normalized_prefix}/"):
        return path
    if not path:
        return normalized_prefix or "/"
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{normalized_prefix}{normalized_path}"


def _collect_router_route_paths(router: APIRouter) -> tuple[str, ...]:
    route_paths: set[str] = set()
    prefix = router.prefix
    for route in router.routes:
        if not isinstance(route, APIRoute | APIWebSocketRoute):
            continue
        for candidate_path in (route.path, route.path_format):
            if not candidate_path:
                continue
            route_paths.add(_join_paths(prefix, candidate_path))
    return tuple(sorted(route_paths))


def build_router_limit_targets(
    routers: ApiRouters,
) -> MappingProxyType[str, RouterLimitTarget]:
    targets: dict[str, RouterLimitTarget] = {}
    for spec in iter_rate_limit_router_sources(routers):
        targets[spec.name] = RouterLimitTarget(
            path_prefix=spec.router.prefix,
            default_stream_paths=normalize_string_sequence(spec.default_stream_paths),
            route_paths=_collect_router_route_paths(spec.router),
        )
    targets[OPENAPI_SCHEMA_RATE_LIMIT_TARGET] = RouterLimitTarget(
        path_prefix="",
        default_stream_paths=(),
        route_paths=tuple(sorted((OPENAI_OPENAPI_SCHEMA_PATH, SOAI_API_OPENAPI_SCHEMA_PATH))),
    )
    return MappingProxyType(targets)


def _gather_stream_paths(
    default_paths: tuple[str, ...],
    override: RateLimitRouterOverride,
) -> tuple[str, ...]:
    if override.stream_paths:
        return override.stream_paths
    return normalize_string_sequence(default_paths)


def _empty_router_override() -> RateLimitRouterOverride:
    return RateLimitRouterOverride(
        default_limit=None,
        stream_limit=None,
        path_limits={},
        stream_paths=(),
    )


def _validate_router_overrides(
    router_overrides: dict[str, RateLimitRouterOverride],
    router_targets: Mapping[str, RouterLimitTarget],
) -> None:
    unknown_routers = tuple(
        router_name for router_name in sorted(router_overrides) if router_name not in router_targets
    )
    if unknown_routers:
        joined = ", ".join(unknown_routers)
        raise ValidationError(f"Unknown API.OPENAI.RATE_LIMITING.ROUTERS entries: {joined}.")
    for router_name, router_config in router_overrides.items():
        target = router_targets[router_name]
        route_paths = frozenset(target.route_paths)
        unknown_paths = tuple(
            path for path in sorted(router_config.path_limits) if path not in route_paths
        )
        if unknown_paths:
            joined = ", ".join(unknown_paths)
            raise ValidationError(f"Unknown rate-limit PATHS for router {router_name}: {joined}.")
        unknown_stream_paths = tuple(
            path for path in sorted(router_config.stream_paths) if path not in route_paths
        )
        if unknown_stream_paths:
            joined = ", ".join(unknown_stream_paths)
            raise ValidationError(
                f"Unknown rate-limit STREAM_PATHS for router {router_name}: {joined}.",
            )


def _validate_unique_target_paths(router_targets: Mapping[str, RouterLimitTarget]) -> None:
    seen_paths: dict[str, str] = {}
    for router_name, target in router_targets.items():
        for route_path in target.route_paths:
            previous_router = seen_paths.get(route_path)
            if previous_router is not None:
                raise StateError(
                    f"Duplicate rate-limit route target path {route_path} in routers {previous_router} and {router_name}.",
                )
            seen_paths[route_path] = router_name


def validate_rate_limit_config_keys(rate_limit_config: Mapping[str, JSONValue]) -> None:
    unexpected_keys: list[str] = []
    for key in rate_limit_config:
        if not isinstance(key, str):
            raise ValidationError("API.OPENAI.RATE_LIMITING keys must be strings.")
        if key not in RATE_LIMIT_CONFIG_KEYS:
            unexpected_keys.append(key)
    if unexpected_keys:
        joined = ", ".join(sorted(unexpected_keys))
        raise ValidationError(f"Unknown API.OPENAI.RATE_LIMITING keys: {joined}.")


def rate_limit_config_signature(rate_limit_config: Mapping[str, JSONValue]) -> str:
    validate_rate_limit_config_keys(rate_limit_config)
    routers = normalize_rate_limit_router_overrides(rate_limit_config.get("ROUTERS"))
    normalized_routers: dict[str, JSONValue] = {}
    for router_name, router_config in routers.items():
        normalized_routers[str(router_name)] = {
            "default": router_config.default_limit,
            "stream": router_config.stream_limit,
            "paths": router_config.path_limits,
            "stream_paths": list(router_config.stream_paths),
        }
    payload = {
        "default": normalize_rate_limit_value(
            rate_limit_config.get("DEFAULT_LIMIT"),
            field_label="API.OPENAI.RATE_LIMITING.DEFAULT_LIMIT",
        ),
        "stream": normalize_rate_limit_value(
            rate_limit_config.get("STREAM_LIMIT"),
            field_label="API.OPENAI.RATE_LIMITING.STREAM_LIMIT",
        ),
        "routers": normalized_routers,
    }
    raw = serialize_json_compact_stable(payload)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _resolve_route_limit(
    route_path: str,
    path_limits: dict[str, str],
    stream_paths: tuple[str, ...],
    router_stream: str | None,
    router_default: str | None,
) -> str | None:
    limit_value = path_limits.get(route_path)
    if not limit_value:
        if stream_paths and route_path in stream_paths and router_stream:
            limit_value = router_stream
        elif router_default:
            limit_value = router_default
    return limit_value


def build_resolved_rate_limit_config(
    rate_limit_config: Mapping[str, JSONValue],
    router_targets: MappingProxyType[str, RouterLimitTarget],
) -> ResolvedRateLimitConfig:
    signature = rate_limit_config_signature(rate_limit_config)
    default_limit = normalize_rate_limit_value(
        rate_limit_config.get("DEFAULT_LIMIT"),
        field_label="API.OPENAI.RATE_LIMITING.DEFAULT_LIMIT",
    )
    stream_limit = normalize_rate_limit_value(
        rate_limit_config.get("STREAM_LIMIT"),
        field_label="API.OPENAI.RATE_LIMITING.STREAM_LIMIT",
    )
    router_overrides = normalize_rate_limit_router_overrides(rate_limit_config.get("ROUTERS"))
    _validate_router_overrides(router_overrides, router_targets)
    _validate_unique_target_paths(router_targets)
    all_path_limits: dict[str, ResolvedPathLimit] = {}
    for name, target in router_targets.items():
        router_config = router_overrides.get(name, _empty_router_override())
        router_default = router_config.default_limit or default_limit
        router_stream = router_config.stream_limit or stream_limit
        stream_paths = _gather_stream_paths(target.default_stream_paths, router_config)
        for route_path in target.route_paths:
            limit_value = _resolve_route_limit(
                route_path,
                router_config.path_limits,
                stream_paths,
                router_stream,
                router_default,
            )
            if not limit_value:
                continue
            rules = parse_rate_limit_rules(limit_value)
            if rules:
                all_path_limits[route_path] = ResolvedPathLimit(
                    limit_string=limit_value,
                    rules=rules,
                )
    return ResolvedRateLimitConfig(
        enabled=True,
        signature=signature,
        path_limits=MappingProxyType(all_path_limits),
    )
