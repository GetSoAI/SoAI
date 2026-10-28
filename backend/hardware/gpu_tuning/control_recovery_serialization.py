"""SoAI - Frozen GPU recovery wire and scope serialization [backend/hardware/gpu_tuning/control_recovery_serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import hashlib
from typing import TYPE_CHECKING

from core.hardware.gpu_recovery_records import (
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from core.serialization.json import serialize_json_compact_stable

if TYPE_CHECKING:
    from core.hardware.gpu_recovery_records import GPURecoveryRecord
    from core.types.json import JSONDict


__all__ = (
    "encode_recovery_record",
    "recovery_scope_digest",
)


def encode_recovery_record(
    record: GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord,
) -> JSONDict:
    if isinstance(record, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord):
        commit = record.legacy_commit
        payload: JSONDict = {
            "type": (
                "startup_recovery"
                if isinstance(record, GPUStartupRecoveryRecord)
                else "startup_legacy_recovery"
            ),
            "startup_operation_id": record.startup_operation_id,
            "device_id": record.device_id,
            "legacy_record": encode_recovery_record(record.legacy_record),
            "legacy_commit": (
                None
                if commit is None
                else {
                    "committed_at": commit.committed_at,
                    "completed_control_state_digest": commit.completed_control_state_digest,
                }
            ),
        }
        if isinstance(record, GPUStartupRecoveryRecord):
            payload["original_record"] = encode_recovery_record(record.original_record)
        return payload
    members: list[JSONDict] = []
    for member in record.members:
        encoded: JSONDict = {
            "field": member.field,
            "member_id": member.member_id,
            "domain_id": member.domain_id,
            "pstate_id": member.pstate_id,
            "original_value": member.original_value,
            "original_mode": member.original_mode,
            "native_unit": member.native_unit,
            "original_observation": member.original_observation.value,
            "effect": member.effect.value,
            "verification": member.verification.value,
            "restoration": member.restoration.value,
            "changed": member.changed,
            "requested_value": member.requested_value,
            "requested_mode": member.requested_mode,
        }
        if member.backend is not None:
            encoded["backend"] = member.backend
        members.append(encoded)
    identity: JSONDict = {
        "uuid": record.physical_identity.uuid,
        "pci_bdf_full": record.physical_identity.pci_bdf_full,
    }
    if record.physical_identity.windows_pnp_instance_id is not None:
        identity["windows_pnp_instance_id"] = record.physical_identity.windows_pnp_instance_id
    payload = {
        "operation_id": record.operation_id,
        "device_id": record.device_id,
        "physical_identity": identity,
        "backend": record.backend,
        "phase": record.phase.value,
        "requested_settings": copy.deepcopy(record.requested_settings),
        "requested_modes": copy.deepcopy(record.requested_modes),
        "requested_units": copy.deepcopy(record.requested_units),
        "members": members,
    }
    if record.pci_bdf_observations is not None:
        payload["pci_bdf_observations"] = list(record.pci_bdf_observations)
    intent = record.commit_intent
    if intent is not None:
        payload["commit_intent"] = {
            "user_fields": list(intent.user_fields),
            "expected_control_state_digest": intent.expected_control_state_digest,
            "slot_id": intent.slot_id,
            "slot_signature": intent.slot_signature,
            "apply_at_boot": intent.apply_at_boot,
        }
    return payload


def recovery_scope_digest(
    record: GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord,
) -> str:
    if isinstance(record, GPUStartupRecoveryRecord):
        return _digest(
            {
                "type": "startup_recovery",
                "startup_operation_id": record.startup_operation_id,
                "device_id": record.device_id,
                "original_scope": recovery_scope_digest(record.original_record),
                "legacy_scope": recovery_scope_digest(record.legacy_record),
            }
        )
    if isinstance(record, GPUStartupLegacyRecoveryRecord):
        return _digest(
            {
                "type": "startup_legacy_recovery",
                "startup_operation_id": record.startup_operation_id,
                "device_id": record.device_id,
                "legacy_scope": recovery_scope_digest(record.legacy_record),
            }
        )
    payload = encode_recovery_record(record)
    payload.pop("phase")
    members: list[JSONDict] = []
    for member in record.members:
        frozen: JSONDict = {
            "field": member.field,
            "member_id": member.member_id,
            "domain_id": member.domain_id,
            "pstate_id": member.pstate_id,
            "backend": member.backend,
            "original_value": member.original_value,
            "original_mode": member.original_mode,
            "native_unit": member.native_unit,
            "original_observation": member.original_observation.value,
            "requested_value": member.requested_value,
            "requested_mode": member.requested_mode,
        }
        members.append(frozen)
    members.sort(key=serialize_json_compact_stable)
    payload["members"] = members
    return _digest(payload)


def _digest(payload: JSONDict) -> str:
    return hashlib.sha256(serialize_json_compact_stable(payload).encode("utf-8")).hexdigest()
