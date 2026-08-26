"""SoAI - Durable mutation admission contracts [backend/core/database/mutation_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = (
    "MutationAdmissionOutcome",
    "MutationAdmissionDraft",
    "MutationAdmissionRequest",
    "MutationClaim",
    "MutationRecoveryCandidate",
    "MutationRecoveryRequiredAdmission",
)


@dataclass(frozen=True, slots=True)
class MutationAdmissionRequest:
    request_id: str
    conflict_keys: tuple[str, ...]
    shared_conflict_keys: tuple[str, ...]
    accepted_task_id: str
    operation_type: str
    target_identity: str
    owner_id: str
    authorization_scope: str
    command_payload: str
    schema_discriminator: str
    recovery_payload_encrypted: str | None
    excluded_target_names: tuple[str, ...]
    supersedes_request_id: str | None = None


@dataclass(frozen=True, slots=True)
class MutationAdmissionDraft:
    request_id: str
    conflict_keys: tuple[str, ...]
    shared_conflict_keys: tuple[str, ...]
    operation_type: str
    target_identity: str
    authorization_scope: str
    command_payload: str
    schema_discriminator: str
    recovery_payload_encrypted: str | None = None
    excluded_target_names: tuple[str, ...] = ()
    supersedes_request_id: str | None = None


@dataclass(frozen=True, slots=True)
class MutationAdmissionOutcome:
    outcome: Literal["accepted", "replay", "conflict"]
    task_id: str


@dataclass(frozen=True, slots=True)
class MutationClaim:
    request_id: str
    task_id: str
    operation_type: str
    target_identity: str
    owner_id: str
    authorization_scope: str
    conflict_keys: tuple[str, ...]
    command_payload: str
    schema_discriminator: str
    recovery_payload_encrypted: str | None
    fencing_token: int
    attempt_count: int
    execution_phase: str = "accepted"
    execution_state: str = "{}"


@dataclass(frozen=True, slots=True)
class MutationRecoveryCandidate:
    request_id: str
    operation_type: str
    conflict_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MutationRecoveryRequiredAdmission:
    request_id: str
    task_id: str
    operation_type: str
    target_identity: str
    conflict_keys: tuple[str, ...]
    command_payload: str
    execution_phase: str
    attempt_count: int
