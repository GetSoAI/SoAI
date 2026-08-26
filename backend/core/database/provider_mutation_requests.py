"""SoAI - Provider mutation contracts [backend/core/database/provider_mutation_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = (
    "ProviderDeleteMutationRequest",
    "ProviderCreateMutationRequest",
    "ProviderMutationOutcome",
    "ProviderMutationReplayRequest",
    "ProviderUpdateMutationRequest",
)


@dataclass(frozen=True, slots=True)
class ProviderUpdateMutationRequest:
    operation_id: str
    owner_id: str
    plugin_name: str
    provider_id: str
    expected_revision: int
    updates_json: str
    validation_status: str
    validation_error: str | None
    validated_at_ms: int | None
    accepted_at_ms: int


@dataclass(frozen=True, slots=True)
class ProviderCreateMutationRequest:
    operation_id: str
    owner_id: str
    plugin_name: str
    provider_id: str
    provider_json: str
    validation_status: str
    validation_error: str | None
    validated_at_ms: int | None
    accepted_at_ms: int


@dataclass(frozen=True, slots=True)
class ProviderDeleteMutationRequest:
    operation_id: str
    owner_id: str
    plugin_name: str
    provider_id: str
    expected_revision: int
    accepted_at_ms: int


@dataclass(frozen=True, slots=True)
class ProviderMutationReplayRequest:
    operation_id: str
    owner_id: str
    operation_type: Literal["create", "update", "delete"]
    plugin_name: str
    provider_id: str
    expected_revision: int
    request_json: str


@dataclass(frozen=True, slots=True)
class ProviderMutationOutcome:
    outcome: Literal["created", "updated", "deleted", "conflict", "stale_revision", "not_found"]
    provider_id: str
    revision: int | None
    provider_json: str | None = None
