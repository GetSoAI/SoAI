"""SoAI - Plugin clone transaction contracts [backend/core/database/clone_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "CLONE_PROVISIONAL_STATE",
    "CloneArtifactRecord",
    "CloneCommitOutboxRecord",
    "CloneCommitRequest",
    "CloneTransactionRecord",
)

CLONE_PROVISIONAL_STATE = "ACTIVATING"


@dataclass(frozen=True, slots=True)
class CloneCommitOutboxRecord:
    event_id: str
    event_type: str
    payload_json: str


@dataclass(frozen=True, slots=True)
class CloneCommitRequest:
    task_id: str
    target_plugin_name: str
    fencing_token: int
    ready_state: str
    completed_at_ms: int
    task_result_json: str
    task_status_message: str
    authoritative_event: CloneCommitOutboxRecord
    domain_events: tuple[CloneCommitOutboxRecord, ...]


@dataclass(frozen=True, slots=True)
class CloneTransactionRecord:
    task_id: str
    source_plugin_name: str
    target_plugin_name: str
    clone_models: bool
    phase: str
    committed: bool


@dataclass(frozen=True, slots=True)
class CloneArtifactRecord:
    artifact_id: int
    artifact_type: str
    staging_path: str
    final_path: str
    state: str
