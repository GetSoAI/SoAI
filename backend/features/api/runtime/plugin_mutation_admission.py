"""SoAI - Plugin mutation admission builders [backend/features/api/runtime/plugin_mutation_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Sequence
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.database.mutation_requests import MutationAdmissionDraft
from core.errors.exceptions import ValidationError
from core.mutations.identifiers import require_mutation_request_id
from core.plugins.clone_configuration import validate_clone_configuration_inputs
from core.plugins.mutation_conflicts import build_plugin_lifecycle_conflict_key
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.security.encryption import encrypt_data
from core.serialization.json import serialize_json_compact_stable
from core.types.json import JSONDict

__all__ = ("build_clone_mutation_admission",)

if TYPE_CHECKING:
    from core.plugins.protocols_instance import ClonableFieldProtocol


_CLONE_OVERRIDE_FINGERPRINT_CONTEXT = b"soai.clone-overrides.v1\x00"


def _fingerprint_clone_overrides(payload: str, secret: str) -> str:
    if not isinstance(secret, str) or not secret:
        raise ValidationError("Clone mutation admission requires a fingerprint secret.")
    return hmac.new(
        secret.encode("utf-8"),
        _CLONE_OVERRIDE_FINGERPRINT_CONTEXT + payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_clone_mutation_admission(
    *,
    request_id: str,
    source_plugin_name: str,
    target_plugin_name: str | None,
    clone_models: bool,
    field_overrides: JSONDict | None,
    clonable_fields: Sequence[ClonableFieldProtocol],
    fernets: Sequence[Fernet],
    fingerprint_secret: str,
    occupied_target_names: Sequence[str],
) -> MutationAdmissionDraft:
    validated_request_id = require_mutation_request_id(request_id)
    source_name = require_portable_plugin_identifier(
        source_plugin_name,
        field_name="plugin_name",
    )
    target_name = (
        require_portable_plugin_identifier(target_plugin_name, field_name="target_name")
        if target_plugin_name is not None
        else None
    )
    validate_clone_configuration_inputs(clonable_fields, field_overrides)
    override_payload_text = (
        serialize_json_compact_stable({"field_overrides": field_overrides})
        if field_overrides is not None
        else None
    )
    override_fingerprint = (
        _fingerprint_clone_overrides(override_payload_text, fingerprint_secret)
        if override_payload_text is not None
        else None
    )
    recovery_payload_text = (
        serialize_json_compact_stable(
            {
                "field_overrides": field_overrides,
                "fingerprint": override_fingerprint,
            }
        )
        if override_fingerprint is not None
        else None
    )
    safe_payload: JSONDict = {
        "plugin_name": source_name,
        "target_name": target_name,
        "clone_models": clone_models,
        "field_override_names": sorted(field_overrides) if field_overrides is not None else [],
        "field_overrides_fingerprint": override_fingerprint,
    }
    recovery_payload = (
        encrypt_data(
            fernets,
            recovery_payload_text,
        )
        if recovery_payload_text is not None
        else None
    )
    excluded_target_names = tuple(
        sorted(
            {
                require_portable_plugin_identifier(
                    name,
                    field_name="occupied_target_name",
                )
                for name in occupied_target_names
            }
        )
    )
    return MutationAdmissionDraft(
        request_id=validated_request_id,
        conflict_keys=(),
        shared_conflict_keys=(build_plugin_lifecycle_conflict_key(source_name),),
        operation_type="plugin_clone",
        target_identity=target_name or source_name,
        authorization_scope="plugin_admin",
        command_payload=serialize_json_compact_stable(safe_payload),
        schema_discriminator="plugin_clone_v1",
        recovery_payload_encrypted=recovery_payload,
        excluded_target_names=excluded_target_names,
    )
