"""SoAI - Browser profile configuration helpers [backend/mcp/tools/browser/profile_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.value_types import ConfigDict, ConfigValue
from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "BrowserProfileConfig",
    "resolve_profile_config",
)


@dataclass(frozen=True, slots=True)
class BrowserProfileConfig:
    name: str
    cdp_url: str | None
    persistence: str
    headless: bool | None
    channel: str | None
    locale: str | None
    timezone_id: str | None
    accept_language: str | None
    viewport_width: int | None
    viewport_height: int | None
    device_scale_factor: float | None


_ALLOWED_CHANNELS: frozenset[str] = frozenset(
    {
        "chrome",
        "chrome-beta",
        "chrome-dev",
        "chrome-canary",
        "msedge",
        "msedge-beta",
        "msedge-dev",
        "msedge-canary",
    },
)


def resolve_profile_config(config: ConfigProtocol, *, profile: str) -> BrowserProfileConfig:
    name = str(profile or "").strip()
    if not name:
        raise ValidationError("profile must be a non-empty string.")
    empty_profiles: ConfigDict = {}
    raw_profiles = (
        config.get("TOOLS.MCP.BROWSER.PROFILES", empty_profiles)
        if config is not None
        else empty_profiles
    )
    if not isinstance(raw_profiles, Mapping):
        raw_profiles = empty_profiles
    entry = raw_profiles.get(name)
    if entry is None:
        return _build_profile_config(
            name=name,
            entry=empty_profiles,
            cdp_url=None,
            persistence="storage_state",
        )
    if not isinstance(entry, Mapping):
        raise ValidationError(f"TOOLS.MCP.BROWSER.PROFILES.{name} must be an object when present.")
    raw_persistence = entry.get("persistence")
    persistence_value = (
        str(raw_persistence or "").strip().lower() if raw_persistence is not None else ""
    )
    if not persistence_value:
        persistence_value = "storage_state"
    if persistence_value not in {"storage_state", "user_data_dir"}:
        raise ValidationError(
            f"TOOLS.MCP.BROWSER.PROFILES.{name}.persistence must be 'storage_state' or 'user_data_dir'.",
        )
    cdp_url_raw = entry.get("cdp_url")
    if cdp_url_raw is None:
        return _build_profile_config(
            name=name,
            entry=entry,
            cdp_url=None,
            persistence=persistence_value,
        )
    if not isinstance(cdp_url_raw, str) or not cdp_url_raw.strip():
        raise ValidationError(
            f"TOOLS.MCP.BROWSER.PROFILES.{name}.cdp_url must be a non-empty string.",
        )
    cdp_url = str(cdp_url_raw).strip()
    headless = _optional_bool(
        entry.get("headless"),
        key=f"TOOLS.MCP.BROWSER.PROFILES.{name}.headless",
    )
    channel = _optional_channel(
        entry.get("channel"),
        key=f"TOOLS.MCP.BROWSER.PROFILES.{name}.channel",
    )
    if headless is not None:
        raise ValidationError(
            f"TOOLS.MCP.BROWSER.PROFILES.{name}.headless is not supported for cdp_url profiles.",
        )
    if channel is not None:
        raise ValidationError(
            f"TOOLS.MCP.BROWSER.PROFILES.{name}.channel is not supported for cdp_url profiles.",
        )
    return _build_profile_config(
        name=name,
        entry=entry,
        cdp_url=cdp_url,
        persistence=persistence_value,
    )


def _build_profile_config(
    *,
    name: str,
    entry: Mapping[str, ConfigValue],
    cdp_url: str | None,
    persistence: str,
) -> BrowserProfileConfig:
    prefix = f"TOOLS.MCP.BROWSER.PROFILES.{name}"
    viewport_width = _optional_int(
        entry.get("viewport_width"),
        key=f"{prefix}.viewport_width",
        minimum=320,
        maximum=7680,
    )
    viewport_height = _optional_int(
        entry.get("viewport_height"),
        key=f"{prefix}.viewport_height",
        minimum=240,
        maximum=4320,
    )
    if (viewport_width is None) != (viewport_height is None):
        raise ValidationError(
            f"{prefix}.viewport_width and {prefix}.viewport_height must be provided together.",
        )
    return BrowserProfileConfig(
        name=name,
        cdp_url=cdp_url,
        persistence=persistence,
        headless=_optional_bool(entry.get("headless"), key=f"{prefix}.headless"),
        channel=_optional_channel(entry.get("channel"), key=f"{prefix}.channel"),
        locale=_optional_text(entry.get("locale"), key=f"{prefix}.locale"),
        timezone_id=_optional_text(entry.get("timezone_id"), key=f"{prefix}.timezone_id"),
        accept_language=_optional_text(
            entry.get("accept_language"),
            key=f"{prefix}.accept_language",
        ),
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        device_scale_factor=_optional_float(
            entry.get("device_scale_factor"),
            key=f"{prefix}.device_scale_factor",
            minimum=0.25,
            maximum=8.0,
        ),
    )


def _optional_text(value: ConfigValue | None, *, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{key} must be a non-empty string when provided.")
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        raise ValidationError(f"{key} must be a non-empty string when provided.")
    return normalized


def _optional_channel(value: ConfigValue | None, *, key: str) -> str | None:
    channel = _optional_text(value, key=key)
    if channel is None:
        return None
    normalized = channel.lower()
    if normalized not in _ALLOWED_CHANNELS:
        allowed = ", ".join(sorted(_ALLOWED_CHANNELS))
        raise ValidationError(f"{key} must be one of: {allowed}.")
    return normalized


def _optional_bool(value: ConfigValue | None, *, key: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValidationError(f"{key} must be a boolean when provided.")
    return bool(value)


def _optional_int(
    value: ConfigValue | None,
    *,
    key: str,
    minimum: int,
    maximum: int,
) -> int | None:
    if value is None:
        return None
    if not is_strict_int(value):
        raise ValidationError(f"{key} must be an integer when provided.")
    parsed = int(value)
    if parsed < minimum or parsed > maximum:
        raise ValidationError(f"{key} must be between {minimum} and {maximum}.")
    return parsed


def _optional_float(
    value: ConfigValue | None,
    *,
    key: str,
    minimum: float,
    maximum: float,
) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValidationError(f"{key} must be a number when provided.")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValidationError(f"{key} must be a finite number when provided.")
    if parsed < minimum or parsed > maximum:
        raise ValidationError(f"{key} must be between {minimum:g} and {maximum:g}.")
    return parsed
