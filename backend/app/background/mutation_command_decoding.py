"""SoAI - Durable mutation command decoding [backend/app/background/mutation_command_decoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from cryptography.fernet import Fernet

from core.database.mutation_requests import MutationClaim
from core.errors.exceptions import StateError, ValidationError
from core.events.types_base import Event, ReplyableCommand
from core.events.types_plugins import (
    ClonePluginCommand,
    InstallPluginBackendCommand,
    RemovePluginBackendCommand,
    UpdatePluginBackendCommand,
)
from core.mutations.edition_composition import DurableMutationComposition
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.runtime.request_context import RequestContext
from core.security.encryption import decrypt_data
from core.serialization.json_parsing import parse_json_dict
from core.types.json import JSONDict, JSONValue

__all__ = ("decode_mutation_command",)


def _require_exact_keys(payload: JSONDict, expected: frozenset[str]) -> None:
    if frozenset(payload) != expected:
        raise StateError("Durable mutation command payload does not match its V1 schema.")


def _require_plugin_name(payload: JSONDict) -> str:
    plugin_name = payload.get("plugin_name")
    if not isinstance(plugin_name, str):
        raise StateError("Durable mutation command is missing its plugin identity.")
    try:
        return require_portable_plugin_identifier(plugin_name, field_name="plugin_name")
    except ValidationError as exception:
        raise StateError("Durable mutation command has an invalid plugin identity.") from exception


def _decode_backend_variant(payload: JSONDict) -> str | None:
    backend_variant_id = payload.get("backend_variant_id")
    if backend_variant_id is None:
        return None
    if not isinstance(backend_variant_id, str) or not backend_variant_id.strip():
        raise StateError("Recovered backend variant identity is invalid.")
    return backend_variant_id


def _decode_backend_command(
    claim: MutationClaim,
    payload: JSONDict,
    context: RequestContext,
    reply_queue: asyncio.Queue[Event],
) -> ReplyableCommand:
    plugin_name = _require_plugin_name(payload)
    if claim.operation_type == "plugin_backend_remove":
        _require_exact_keys(payload, frozenset(("delete_models", "plugin_name")))
        delete_models = payload["delete_models"]
        if not isinstance(delete_models, bool):
            raise StateError("Recovered delete_models must be a boolean.")
        return RemovePluginBackendCommand(
            reply_channel=reply_queue,
            context=context,
            plugin_name=plugin_name,
            delete_models=delete_models,
        )
    _require_exact_keys(payload, frozenset(("backend_variant_id", "plugin_name")))
    backend_variant_id = _decode_backend_variant(payload)
    if claim.operation_type == "plugin_backend_install":
        return InstallPluginBackendCommand(
            reply_channel=reply_queue,
            context=context,
            plugin_name=plugin_name,
            backend_variant_id=backend_variant_id,
        )
    if claim.operation_type == "plugin_backend_update":
        return UpdatePluginBackendCommand(
            reply_channel=reply_queue,
            context=context,
            plugin_name=plugin_name,
            backend_variant_id=backend_variant_id,
        )
    raise StateError("Unsupported durable backend mutation operation.")


def _decode_override_names(value: JSONValue) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise StateError("Recovered clone override names are invalid.")
    decoded_names: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise StateError("Recovered clone override names are invalid.")
        decoded_names.append(item)
    names = tuple(decoded_names)
    if names != tuple(sorted(set(names))) or any(not name for name in names):
        raise StateError("Recovered clone override names are not canonical.")
    return names


def _decode_override_fingerprint(value: JSONValue, *, encrypted: bool) -> str | None:
    if not encrypted:
        if value is not None:
            raise StateError("Recovered clone override fingerprint is unexpected.")
        return None
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise StateError("Recovered clone override fingerprint is invalid.")
    return value


def _decrypt_clone_overrides(
    claim: MutationClaim,
    names: tuple[str, ...],
    fingerprint: str | None,
    fernets: Sequence[Fernet],
) -> JSONDict | None:
    encrypted = claim.recovery_payload_encrypted
    if encrypted is None:
        if names:
            raise StateError("Recovered clone overrides are missing encrypted data.")
        return None
    decrypted = decrypt_data(fernets, encrypted)
    if decrypted is None:
        raise StateError("Recovered clone override ciphertext is empty.")
    recovery = parse_json_dict(decrypted, field="clone_recovery_payload")
    _require_exact_keys(recovery, frozenset(("field_overrides", "fingerprint")))
    if recovery["fingerprint"] != fingerprint:
        raise StateError("Recovered clone override fingerprint does not match encrypted data.")
    overrides = recovery["field_overrides"]
    if not isinstance(overrides, dict):
        raise StateError("Recovered clone field overrides are invalid.")
    if tuple(sorted(overrides)) != names:
        raise StateError("Recovered clone override identities do not match the safe payload.")
    return overrides


def _decode_clone_command(
    claim: MutationClaim,
    payload: JSONDict,
    context: RequestContext,
    reply_queue: asyncio.Queue[Event],
    fernets: Sequence[Fernet],
) -> ClonePluginCommand:
    _require_exact_keys(
        payload,
        frozenset(
            (
                "clone_models",
                "field_override_names",
                "field_overrides_fingerprint",
                "plugin_name",
                "target_name",
            )
        ),
    )
    plugin_name = _require_plugin_name(payload)
    clone_models = payload["clone_models"]
    if not isinstance(clone_models, bool):
        raise StateError("Recovered clone_models must be a boolean.")
    target_value = payload["target_name"]
    if target_value is not None and not isinstance(target_value, str):
        raise StateError("Recovered clone target identity is invalid.")
    try:
        target_name = require_portable_plugin_identifier(
            claim.target_identity,
            field_name="target_name",
        )
    except ValidationError as exception:
        raise StateError("Recovered clone target identity is invalid.") from exception
    if target_value is not None and target_value != target_name:
        raise StateError("Recovered clone target identity does not match the accepted request.")
    names = _decode_override_names(payload["field_override_names"])
    fingerprint = _decode_override_fingerprint(
        payload["field_overrides_fingerprint"],
        encrypted=claim.recovery_payload_encrypted is not None,
    )
    return ClonePluginCommand(
        reply_channel=reply_queue,
        context=context,
        plugin_name=plugin_name,
        target_name=target_name,
        clone_models=clone_models,
        field_overrides=_decrypt_clone_overrides(claim, names, fingerprint, fernets),
    )


def decode_mutation_command(
    claim: MutationClaim,
    *,
    context: RequestContext,
    reply_queue: asyncio.Queue[Event],
    fernets: Sequence[Fernet],
    durable_mutations: DurableMutationComposition,
) -> ReplyableCommand:
    try:
        payload = parse_json_dict(claim.command_payload, field="mutation_command_payload")
    except ValidationError as exception:
        raise StateError("Durable mutation command payload is corrupt.") from exception
    expected_schema = f"{claim.operation_type}_v1"
    if claim.schema_discriminator != expected_schema:
        raise StateError("Durable mutation schema discriminator is inconsistent.")
    if claim.operation_type == "plugin_clone":
        return _decode_clone_command(claim, payload, context, reply_queue, fernets)
    operation_matches = durable_mutations.operation_matches
    decode_extension = durable_mutations.decode_command
    if operation_matches is not None and operation_matches(claim.operation_type):
        if decode_extension is None:
            raise StateError("Edition mutation decoder is unavailable.")
        decoded_command = decode_extension(
            claim,
            context=context,
            reply_queue=reply_queue,
            fernets=fernets,
        )
        if decoded_command is None:
            raise StateError("Edition mutation decoder rejected its operation.")
        return decoded_command
    return _decode_backend_command(claim, payload, context, reply_queue)
