"""SoAI - WebUI notification source visibility helpers [backend/core/notifications/notification_source_visibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.notifications.notification_contracts import (
    PLUGIN_CIRCUIT_BREAKER_NOTIFICATION_SOURCE,
)
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "normalize_notification_excluded_sources",
    "notification_source_is_visible",
    "resolve_notification_excluded_sources",
)


def resolve_notification_excluded_sources(*, can_read_plugins: bool) -> frozenset[str]:
    if can_read_plugins:
        return frozenset()
    return frozenset({PLUGIN_CIRCUIT_BREAKER_NOTIFICATION_SOURCE})


def normalize_notification_excluded_sources(sources: frozenset[str]) -> tuple[str, ...]:
    normalized_sources: list[str] = []
    for source in sources:
        normalized = coerce_optional_trimmed_str(source)
        if normalized is None:
            raise ValidationError("excluded_sources contains an invalid source.")
        if normalized not in normalized_sources:
            normalized_sources.append(normalized)
    return tuple(normalized_sources)


def notification_source_is_visible(
    source: str | None,
    excluded_sources: frozenset[str],
) -> bool:
    normalized_source = coerce_optional_trimmed_str(source)
    if normalized_source is None:
        return True
    normalized_excluded_sources = normalize_notification_excluded_sources(excluded_sources)
    return normalized_source not in normalized_excluded_sources
