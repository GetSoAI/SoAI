"""SoAI - External provider API name conflict checks [backend/features/api/runtime/external_provider_names.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable

from core.models.external_provider_record import (
    ExternalProviderInternalRecord,
    ExternalProviderRecord,
    normalize_external_provider_name,
)
from core.types.json import JSONValue

__all__ = ("has_external_provider_name_conflict",)


def has_external_provider_name_conflict(
    providers: Iterable[ExternalProviderRecord | ExternalProviderInternalRecord],
    provider_name: JSONValue,
    *,
    ignored_provider_id: str | None = None,
) -> bool:
    normalized_name = normalize_external_provider_name(provider_name)
    if normalized_name is None:
        return False
    ignored_id = ignored_provider_id.strip() if isinstance(ignored_provider_id, str) else ""
    for provider in providers:
        if ignored_id and provider.get("id") == ignored_id:
            continue
        if normalize_external_provider_name(provider.get("name")) == normalized_name:
            return True
    return False
