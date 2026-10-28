"""SoAI - Fenced backend update execution and recovery [backend/plugins/actions/backend_update_checkpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace

from core.concurrency.cancellation_cleanup import cancellation_cleanup
from core.errors.exceptions import StateError
from core.events.types_plugins import UpdatePluginBackendCommand
from core.plugins.backend_update_records import BackendUpdateIdentity
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_dict
from core.timing.epoch import epoch_ms
from plugins.manager.backend_update_automatic import require_automatic_update_policy
from plugins.manager.backend_update_containment import contain_backend_update_worker
from plugins.manager.backend_update_identity import capture_backend_update_identity
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = (
    "advance_backend_update",
    "contain_backend_update",
    "prepare_backend_update",
    "require_backend_update_identity",
)


async def advance_backend_update(
    manager: PluginManagerRuntimeProtocol,
    command: UpdatePluginBackendCommand,
    next_phase: str,
) -> None:
    claim = command.mutation_claim
    if claim is None:
        return
    if not await manager.dependencies.infrastructure.task_registry.database_tasks.advance_mutation_execution(
        claim.task_id,
        claim.fencing_token,
        expected_phase=claim.execution_phase,
        next_phase=next_phase,
        execution_state=claim.execution_state,
        now_ms=epoch_ms(),
    ):
        raise StateError("Backend update execution ownership changed.")
    command.mutation_claim = replace(claim, execution_phase=next_phase)


def _checkpoint_identity(command: UpdatePluginBackendCommand) -> BackendUpdateIdentity:
    claim = command.mutation_claim
    if claim is None:
        raise StateError("Backend update recovery requires a durable claim.")
    snapshot = parse_json_dict(
        claim.execution_state, field="backend_update_execution", reject_duplicate_keys=True
    )
    if frozenset(snapshot) != {
        "package_hash",
        "configuration_hash",
        "backend_variant_id",
        "requested_variant_id",
    }:
        raise StateError("Backend update execution checkpoint is unsupported.")
    package_hash = snapshot["package_hash"]
    configuration_hash = snapshot["configuration_hash"]
    backend_variant_id = snapshot["backend_variant_id"]
    if (
        not isinstance(package_hash, str)
        or (configuration_hash is not None and not isinstance(configuration_hash, str))
        or not isinstance(backend_variant_id, str)
        or snapshot["requested_variant_id"] != command.backend_variant_id
    ):
        raise StateError("Backend update execution identity is invalid.")
    return BackendUpdateIdentity(
        command.plugin_name, package_hash, configuration_hash, backend_variant_id
    )


async def require_backend_update_identity(
    manager: PluginManagerRuntimeProtocol,
    command: UpdatePluginBackendCommand,
) -> None:
    if command.mutation_claim is None:
        return
    identity = await capture_backend_update_identity(
        manager, command.plugin_name, require_loaded_hash=True
    )
    checkpoint = _checkpoint_identity(command)
    if command.mutation_claim.execution_phase in {"callback_succeeded", "verified"}:
        checkpoint = replace(checkpoint, configuration_hash=identity.configuration_hash)
    else:
        await require_automatic_update_policy(manager, command, before_execution=False)
    if identity != checkpoint:
        raise StateError("Backend update identity changed after acceptance.")


async def prepare_backend_update(
    manager: PluginManagerRuntimeProtocol,
    command: UpdatePluginBackendCommand,
) -> None:
    claim = command.mutation_claim
    if claim is not None:
        context = command.context
        if (
            context is None
            or context.task_id != claim.task_id
            or context.mutation_fencing_token != claim.fencing_token
            or claim.operation_type != "plugin_backend_update"
            or claim.target_identity != command.plugin_name
        ):
            raise StateError("Backend update claim does not match its command.")
        if claim.execution_phase != "accepted":
            if claim.execution_phase not in {"execution_started", "callback_succeeded", "verified"}:
                raise StateError("Backend update recovery checkpoint requires attention.")
            _checkpoint_identity(command)
            await cancellation_cleanup(contain_backend_update_worker(manager, command.plugin_name))
            return
        if claim.attempt_count != 1:
            await advance_backend_update(manager, command, "recovery_required")
            raise StateError("Recovered legacy backend update requires inspection before retry.")
    await require_automatic_update_policy(manager, command, before_execution=True)
    config_manager = manager.dependencies.infrastructure.config_manager
    async with config_manager.plugin_config_mutation_scope(
        command.plugin_name, operation="plugins.actions.backend_update.checkpoint"
    ):
        identity = await capture_backend_update_identity(
            manager, command.plugin_name, require_loaded_hash=True
        )
        database = manager.dependencies.databases.plugins
        await database.materialize_backend_update(identity)
        await database.invalidate_backend_update(command.plugin_name)
        if claim is not None:
            command.mutation_claim = replace(
                claim,
                execution_state=serialize_json_compact_stable(
                    {
                        "package_hash": identity.package_hash,
                        "configuration_hash": identity.configuration_hash,
                        "backend_variant_id": identity.backend_variant_id,
                        "requested_variant_id": command.backend_variant_id,
                    }
                ),
            )
            await advance_backend_update(manager, command, "execution_started")


async def contain_backend_update(
    manager: PluginManagerRuntimeProtocol,
    command: UpdatePluginBackendCommand,
) -> None:
    await cancellation_cleanup(contain_backend_update_worker(manager, command.plugin_name))
    if command.mutation_claim is not None:
        await advance_backend_update(manager, command, "contained_failure")
