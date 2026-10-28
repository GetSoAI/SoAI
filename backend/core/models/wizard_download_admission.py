"""SoAI - Wizard local model download admission [backend/core/models/wizard_download_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.database.mutation_requests import MutationAdmissionDraft
from core.errors.exceptions import ValidationError
from core.mutations.identifiers import require_mutation_request_id
from core.plugins.mutation_conflicts import build_plugin_lifecycle_conflict_key
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.serialization.json import serialize_json_compact_stable
from core.types.json import JSONValue

__all__ = ("build_wizard_download_admission",)


def build_wizard_download_admission(
    request_id: str,
    owner_id: str,
    command_fields: Mapping[str, JSONValue],
    previous_task_id: str | None,
) -> MutationAdmissionDraft:
    plugin_name = command_fields.get("plugin_name")
    model_id = command_fields.get("model_id")
    if not isinstance(plugin_name, str) or not isinstance(model_id, str) or not model_id.strip():
        raise ValidationError("Wizard download requires a plugin and model identity.")
    plugin_name = require_portable_plugin_identifier(plugin_name, field_name="plugin_name")
    previous = (
        require_mutation_request_id(previous_task_id) if previous_task_id is not None else None
    )
    return MutationAdmissionDraft(
        request_id=require_mutation_request_id(request_id),
        conflict_keys=(f"wizard_model_download:{owner_id}",),
        shared_conflict_keys=(build_plugin_lifecycle_conflict_key(plugin_name),),
        operation_type="wizard_model_download",
        target_identity=plugin_name,
        authorization_scope="model_admin",
        command_payload=serialize_json_compact_stable(dict(command_fields)),
        schema_discriminator="wizard_model_download_v1",
        supersedes_request_id=previous,
    )
