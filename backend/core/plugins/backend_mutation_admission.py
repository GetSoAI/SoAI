"""SoAI - Durable plugin backend mutation admission [backend/core/plugins/backend_mutation_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal

from core.database.mutation_requests import MutationAdmissionDraft
from core.errors.exceptions import ValidationError
from core.events.types_base import Event
from core.events.types_plugins import (
    InstallPluginBackendCommand,
    RemovePluginBackendCommand,
    UpdatePluginBackendCommand,
)
from core.mutations.identifiers import require_mutation_request_id
from core.plugins.mutation_conflicts import build_plugin_lifecycle_conflict_key
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.serialization.json import serialize_json_compact_stable
from core.types.json import JSONDict, JSONValue

__all__ = ("build_backend_mutation_admission", "resolve_backend_mutation_operation")

if TYPE_CHECKING:
    BackendMutationType = Literal["install_backend", "remove_backend", "update_backend"]


def resolve_backend_mutation_operation(command_type: type[Event]) -> BackendMutationType:
    if command_type is InstallPluginBackendCommand:
        return "install_backend"
    if command_type is RemovePluginBackendCommand:
        return "remove_backend"
    if command_type is UpdatePluginBackendCommand:
        return "update_backend"
    raise ValidationError("Unsupported durable plugin backend mutation command.")


def _resolve_backend_mutation_schema(operation_type: BackendMutationType) -> tuple[str, str]:
    if operation_type == "install_backend":
        return "plugin_backend_install", "plugin_backend_install_v1"
    if operation_type == "remove_backend":
        return "plugin_backend_remove", "plugin_backend_remove_v1"
    if operation_type == "update_backend":
        return "plugin_backend_update", "plugin_backend_update_v1"
    raise ValidationError("Unsupported durable plugin backend mutation operation.")


def build_backend_mutation_admission(
    *,
    request_id: str,
    plugin_name: str,
    operation_type: BackendMutationType,
    command_fields: Mapping[str, JSONValue],
) -> MutationAdmissionDraft:
    validated_request_id = require_mutation_request_id(request_id)
    normalized_plugin_name = require_portable_plugin_identifier(
        plugin_name,
        field_name="plugin_name",
    )
    canonical_operation, schema_discriminator = _resolve_backend_mutation_schema(operation_type)
    payload: JSONDict = {"plugin_name": normalized_plugin_name}
    payload.update(command_fields)
    return MutationAdmissionDraft(
        request_id=validated_request_id,
        conflict_keys=(build_plugin_lifecycle_conflict_key(normalized_plugin_name),),
        shared_conflict_keys=(),
        operation_type=canonical_operation,
        target_identity=normalized_plugin_name,
        authorization_scope="plugin_admin",
        command_payload=serialize_json_compact_stable(payload),
        schema_discriminator=schema_discriminator,
    )
