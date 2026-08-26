"""SoAI - Rate limit override normalization [backend/features/api/rate_limiting/rate_limit_overrides.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue

__all__ = (
    "RateLimitRouterOverride",
    "normalize_rate_limit_router_override",
    "normalize_rate_limit_router_overrides",
    "normalize_rate_limit_value",
)

ROUTER_OVERRIDE_KEYS: frozenset[str] = frozenset(
    {"DEFAULT_LIMIT", "STREAM_LIMIT", "PATHS", "STREAM_PATHS"},
)


@dataclass(frozen=True, slots=True)
class RateLimitRouterOverride:
    default_limit: str | None
    stream_limit: str | None
    path_limits: dict[str, str]
    stream_paths: tuple[str, ...]


def normalize_rate_limit_value(value: JSONValue, *, field_label: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    raise ValidationError(f"{field_label} must be a string.")


def _build_path_limit_map(raw: JSONValue) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValidationError("Router PATHS must be a mapping.")
    result: dict[str, str] = {}
    for path, limit_value in raw.items():
        if not isinstance(path, str):
            raise ValidationError("Rate limit path keys must be strings.")
        normalized = normalize_rate_limit_value(
            limit_value,
            field_label=f"Rate limit for path {path}",
        )
        if normalized:
            result[path] = normalized
    return result


def _normalize_stream_paths(raw: JSONValue) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        stripped = raw.strip()
        return (stripped,) if stripped else ()
    if not isinstance(raw, list):
        raise ValidationError("Router STREAM_PATHS must be a string or a list of strings.")
    normalized: list[str] = []
    for value in raw:
        if not isinstance(value, str):
            raise ValidationError("Router STREAM_PATHS entries must be strings.")
        stripped = value.strip()
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    return tuple(normalized)


def _validate_router_override_keys(router_config: Mapping[str, JSONValue]) -> None:
    unexpected_keys: list[str] = []
    for key in router_config:
        if not isinstance(key, str):
            raise ValidationError("Rate limit router config keys must be strings.")
        if key not in ROUTER_OVERRIDE_KEYS:
            unexpected_keys.append(key)
    if unexpected_keys:
        joined = ", ".join(sorted(unexpected_keys))
        raise ValidationError(f"Unknown rate limit router config keys: {joined}.")


def normalize_rate_limit_router_override(raw: JSONValue) -> RateLimitRouterOverride:
    if not isinstance(raw, Mapping):
        raise ValidationError("Rate limit router config must be a mapping.")
    router_config = raw
    _validate_router_override_keys(router_config)
    return RateLimitRouterOverride(
        default_limit=normalize_rate_limit_value(
            router_config.get("DEFAULT_LIMIT"),
            field_label="Router DEFAULT_LIMIT",
        ),
        stream_limit=normalize_rate_limit_value(
            router_config.get("STREAM_LIMIT"),
            field_label="Router STREAM_LIMIT",
        ),
        path_limits=_build_path_limit_map(router_config.get("PATHS")),
        stream_paths=_normalize_stream_paths(router_config.get("STREAM_PATHS")),
    )


def normalize_rate_limit_router_overrides(
    raw: JSONValue,
) -> dict[str, RateLimitRouterOverride]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValidationError("API.OPENAI.RATE_LIMITING.ROUTERS must be a mapping.")
    routers = raw
    normalized: dict[str, RateLimitRouterOverride] = {}
    router_names: list[str] = []
    for router_name in routers:
        if not isinstance(router_name, str):
            raise ValidationError("Rate limit router names must be strings.")
        router_names.append(router_name)
    for router_name in sorted(router_names):
        normalized[router_name] = normalize_rate_limit_router_override(routers.get(router_name))
    return normalized
