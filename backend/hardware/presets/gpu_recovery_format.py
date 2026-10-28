"""SoAI - Durable GPU recovery record grammar [backend/hardware/presets/gpu_recovery_format.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_operation_types import GPUControlCommitIntent
from core.hardware.gpu_physical_identity import GPUPhysicalIdentity
from core.hardware.gpu_recovery_records import (
    GPUEffectState,
    GPUOriginalObservationState,
    GPURecoveryMember,
    GPURecoveryPhase,
    GPURecoveryRecord,
    GPURestorationState,
    GPUStartupLegacyCommit,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
    GPUVerificationState,
)
from core.types.json_value import require_json_dict
from core.validation.record_fields import require_number, require_optional_bool
from core.validation.strict_integer import is_strict_int
from core.validation.strict_numbers import require_optional_non_negative_int_strict
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.presets.gpu_recovery_policy import validate_recovery_requested_values

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("decode_gpu_recovery_record",)

_RECOVERY_FIELDS = frozenset(
    (
        "operation_id",
        "device_id",
        "physical_identity",
        "backend",
        "phase",
        "requested_settings",
        "requested_modes",
        "requested_units",
        "members",
    )
)
_MEMBER_FIELDS = frozenset(
    (
        "field",
        "member_id",
        "domain_id",
        "pstate_id",
        "original_value",
        "original_mode",
        "native_unit",
        "original_observation",
        "effect",
        "verification",
        "restoration",
    )
)


def decode_gpu_recovery_record(
    device_id: str,
    value: JSONValue,
) -> GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord:
    record = require_json_dict(value, label="GPU recovery record")
    if "type" not in record:
        return _decode_plain_recovery(device_id, record)
    required_fields = {
        "type",
        "startup_operation_id",
        "device_id",
        "legacy_record",
        "legacy_commit",
    }
    if record["type"] == "startup_recovery":
        required_fields.add("original_record")
    elif record["type"] != "startup_legacy_recovery":
        raise ValidationError("GPU startup recovery discriminator is invalid.")
    if set(record) != required_fields or record["device_id"] != device_id:
        raise ValidationError("GPU startup recovery fields or device identity are invalid.")
    commit = _decode_startup_legacy_commit(record["legacy_commit"])
    if record["type"] == "startup_legacy_recovery":
        return GPUStartupLegacyRecoveryRecord(
            startup_operation_id=_text(
                record["startup_operation_id"], "startup operation identifier"
            ),
            device_id=_text(record["device_id"], "startup device identifier"),
            legacy_record=_decode_plain_recovery(device_id, record["legacy_record"]),
            legacy_commit=commit,
        )
    return GPUStartupRecoveryRecord(
        startup_operation_id=_text(record["startup_operation_id"], "startup operation identifier"),
        device_id=_text(record["device_id"], "startup device identifier"),
        original_record=_decode_plain_recovery(device_id, record["original_record"]),
        legacy_record=_decode_plain_recovery(device_id, record["legacy_record"]),
        legacy_commit=commit,
    )


def _decode_startup_legacy_commit(value: JSONValue) -> GPUStartupLegacyCommit | None:
    if value is None:
        return None
    encoded = require_json_dict(value, label="GPU startup legacy commit")
    if set(encoded) != {"committed_at", "completed_control_state_digest"}:
        raise ValidationError("GPU startup legacy commit fields are invalid.")
    return GPUStartupLegacyCommit(
        committed_at=_text(encoded["committed_at"], "startup committed timestamp"),
        completed_control_state_digest=_text(
            encoded["completed_control_state_digest"], "startup control digest"
        ),
    )


def _text(value: JSONValue, label: str) -> str:
    return require_canonical_trimmed_json_text(
        value, error_message=f"Invalid GPU recovery {label}."
    )


def _decode_plain_recovery(device_id: str, value: JSONValue) -> GPURecoveryRecord:
    record = require_json_dict(value, label="GPU recovery record")
    if (
        not _RECOVERY_FIELDS.issubset(record)
        or set(record) - _RECOVERY_FIELDS - {"pci_bdf_observations", "commit_intent"}
        or record.get("device_id") != device_id
    ):
        raise ValidationError("GPU recovery record fields or device identity are invalid.")
    identity = require_json_dict(
        record["physical_identity"], label="GPU recovery physical identity"
    )
    if set(identity) not in (
        {"uuid", "pci_bdf_full"},
        {"uuid", "pci_bdf_full", "windows_pnp_instance_id"},
    ):
        raise ValidationError("GPU recovery physical identity fields are invalid.")
    uuid_value, pci_value = identity["uuid"], identity["pci_bdf_full"]
    uuid = _text(uuid_value, "UUID") if uuid_value is not None else None
    pci = _text(pci_value, "PCI") if pci_value is not None else None
    pnp_instance = (
        _text(identity["windows_pnp_instance_id"], "Windows PNP instance")
        if "windows_pnp_instance_id" in identity
        else None
    )
    physical_identity = GPUPhysicalIdentity(
        uuid=uuid, pci_bdf_full=pci, windows_pnp_instance_id=pnp_instance
    )
    observations: tuple[str, ...] | None = None
    if "pci_bdf_observations" in record:
        raw_observations = record["pci_bdf_observations"]
        if not isinstance(raw_observations, list):
            raise ValidationError("GPU recovery actual PCI observations require a list.")
        observations = tuple(_text(value, "PCI observation") for value in raw_observations)
        physical_identity.validate_observations(observations)
    settings = require_json_dict(record["requested_settings"], label="GPU recovery settings")
    modes = require_json_dict(record["requested_modes"], label="GPU recovery modes")
    units = require_json_dict(record["requested_units"], label="GPU recovery units")
    if not settings or set(modes) != set(settings) or set(units) != set(settings):
        raise ValidationError("GPU recovery settings require matching explicit modes and units.")
    members_value = record["members"]
    if not isinstance(members_value, list) or not members_value:
        raise ValidationError("GPU recovery requires native member observations.")
    members = tuple(_decode_member(member) for member in members_value)
    if any(member.field not in settings for member in members):
        raise ValidationError("GPU recovery member must belong to the requested fields.")
    if set(settings) != {member.field for member in members}:
        raise ValidationError("Every GPU recovery requested field requires native member evidence.")
    validate_recovery_requested_values(settings, modes, units, members)
    member_keys = {
        (member.backend, member.field, member.member_id, member.domain_id, member.pstate_id)
        for member in members
    }
    if len(member_keys) != len(members):
        raise ValidationError("GPU recovery contains duplicate native members.")
    return GPURecoveryRecord(
        operation_id=_text(record["operation_id"], "operation identifier"),
        device_id=_text(record["device_id"], "device identifier"),
        physical_identity=physical_identity,
        backend=_text(record["backend"], "backend"),
        phase=GPURecoveryPhase(_text(record["phase"], "phase")),
        requested_settings=copy.deepcopy(settings),
        requested_modes=copy.deepcopy(modes),
        requested_units=copy.deepcopy(units),
        members=members,
        pci_bdf_observations=observations,
        commit_intent=_decode_commit_intent(record.get("commit_intent")),
    )


def _decode_commit_intent(value: JSONValue) -> GPUControlCommitIntent | None:
    if value is None:
        return None
    intent = require_json_dict(value, label="GPU commit intent")
    if set(intent) != {
        "user_fields",
        "expected_control_state_digest",
        "slot_id",
        "slot_signature",
        "apply_at_boot",
    }:
        raise ValidationError("GPU commit intent fields are invalid.")
    fields = intent["user_fields"]
    if not isinstance(fields, list):
        raise ValidationError("GPU commit user fields require a list.")
    slot_id = intent["slot_id"]
    signature = intent["slot_signature"]
    if slot_id is not None and not isinstance(slot_id, str):
        raise ValidationError("GPU commit slot identifier must be text or null.")
    if signature is not None and not isinstance(signature, str):
        raise ValidationError("GPU commit slot signature must be text or null.")
    return GPUControlCommitIntent(
        user_fields=tuple(_text(field, "commit user field") for field in fields),
        expected_control_state_digest=_text(
            intent["expected_control_state_digest"], "control digest"
        ),
        slot_id=slot_id,
        slot_signature=signature,
        apply_at_boot=require_optional_bool(
            intent["apply_at_boot"], label="GPU commit boot intent", build_error=ValidationError
        ),
    )


def _decode_member(value: JSONValue) -> GPURecoveryMember:
    member = require_json_dict(value, label="GPU recovery native member")
    if not _MEMBER_FIELDS.issubset(member) or set(member) - _MEMBER_FIELDS - {
        "backend",
        "changed",
        "requested_value",
        "requested_mode",
    }:
        raise ValidationError("GPU recovery native member fields are invalid.")
    requested_value = member.get("requested_value")
    requested_scalar = (
        None
        if requested_value is None
        else require_number(
            requested_value, label="GPU recovery requested value", build_error=ValidationError
        )
    )
    requested_mode = member.get("requested_mode")
    if requested_mode is not None and not is_strict_int(requested_mode):
        requested_mode = _text(requested_mode, "requested mode")
    original_value = member["original_value"]
    numeric_value = (
        None
        if original_value is None
        else require_number(
            original_value, label="GPU recovery original value", build_error=ValidationError
        )
    )
    mode = member["original_mode"]
    if mode is not None and not is_strict_int(mode) and not isinstance(mode, str):
        raise ValidationError("GPU recovery original mode is invalid.")
    original_mode: int | str | None = mode
    observation = GPUOriginalObservationState(_text(member["original_observation"], "observation"))
    if (
        observation == GPUOriginalObservationState.OBSERVED
        and numeric_value is None
        and mode is None
    ):
        raise ValidationError("Observed GPU recovery original must contain a value or mode.")
    if observation != GPUOriginalObservationState.OBSERVED and (
        numeric_value is not None or mode is not None
    ):
        raise ValidationError("Unavailable GPU recovery original cannot contain invented values.")
    restoration = GPURestorationState(_text(member["restoration"], "restoration"))
    if (
        restoration == GPURestorationState.RESTORED
        and observation != GPUOriginalObservationState.OBSERVED
    ):
        raise ValidationError("GPU recovery cannot claim restoration of an unknown original.")
    return GPURecoveryMember(
        field=_text(member["field"], "field"),
        member_id=_text(member["member_id"], "member identifier"),
        domain_id=require_optional_non_negative_int_strict(
            member["domain_id"], error_message="Invalid GPU recovery domain."
        ),
        pstate_id=require_optional_non_negative_int_strict(
            member["pstate_id"], error_message="Invalid GPU recovery Pstate."
        ),
        original_value=numeric_value,
        original_mode=original_mode,
        native_unit=_text(member["native_unit"], "native unit"),
        original_observation=observation,
        effect=GPUEffectState(_text(member["effect"], "effect")),
        verification=GPUVerificationState(_text(member["verification"], "verification")),
        restoration=restoration,
        backend=_text(member["backend"], "member backend") if "backend" in member else None,
        changed=require_optional_bool(
            member.get("changed"), label="GPU recovery changed", build_error=ValidationError
        ),
        requested_value=requested_scalar,
        requested_mode=requested_mode,
    )
