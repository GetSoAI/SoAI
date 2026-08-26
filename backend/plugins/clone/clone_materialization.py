"""SoAI - Clone staging, publication, and commit materialization [backend/plugins/clone/clone_materialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_and_wait,
)
from core.errors.exceptions import StateError
from core.plugins.file_suffixes import PLUGIN_CONFIG_FILE_SUFFIX, PLUGIN_FILE_SUFFIX
from core.plugins.protocols_clone_database import DatabasePluginCloneTransactionsProtocol
from core.runtime.request_context import RequestContext
from core.types.json import JSONDict
from plugins.clone.artifact_ownership import publish_file_no_clobber
from plugins.clone.clone_activation import (
    commit_clone_activation,
    prepare_clone_activation,
    record_clone_runtime_artifacts,
)
from plugins.clone.clone_model_copy import copy_directory_with_progress
from plugins.clone.clone_plan import ClonePlan
from plugins.clone.clone_storage_reservation import CloneStorageReservation
from plugins.clone.directory_artifact_publication import claim_directory_publication
from plugins.clone.staging_artifact_ownership import (
    claim_staging_artifact_ownership,
    record_staging_artifact_ownership,
)
from plugins.clone_paths import retarget_cloned_model_paths
from plugins.clone_plugin_file import clone_plugin_file
from plugins.fs_permissions import ensure_correct_permissions
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol
from plugins.protocols_internal.task_progress.internal_protocols import TaskProgressSenderProtocol

if TYPE_CHECKING:
    from core.events.types_base import Event

__all__ = ("materialize_clone",)


async def _require_artifact_transition(
    repository: DatabasePluginCloneTransactionsProtocol,
    task_id: str,
    artifact_id: int,
    current_state: str,
    following_state: str,
) -> None:
    if not await repository.transition_artifact(
        task_id,
        artifact_id,
        current_state,
        following_state,
    ):
        raise StateError("Clone artifact journal transition was rejected.")


async def _require_phase_transition(
    repository: DatabasePluginCloneTransactionsProtocol,
    task_id: str,
    current_phase: str,
    following_phase: str,
) -> None:
    if not await repository.transition(task_id, current_phase, following_phase):
        raise StateError("Clone transaction phase transition was rejected.")


async def _run_publication(call: Awaitable[None]) -> None:
    await uncancel_and_wait(call)
    if current_task_has_pending_cancellation():
        raise asyncio.CancelledError


async def materialize_clone(
    plugin_manager: PluginManagerRuntimeProtocol,
    *,
    plan: ClonePlan,
    reply_channel: asyncio.Queue[Event],
    task_id: str,
    cloned_config: JSONDict,
    progress_callback: TaskProgressSenderProtocol,
    storage_reservation: CloneStorageReservation,
    fencing_token: int,
    context: RequestContext | None,
) -> str:
    repository = plugin_manager.dependencies.databases.plugins.clone_transactions
    plugin_directory = plugin_manager.paths.plugin_directory
    package_staging = f"{plan.target_plugin_file}.clone-{task_id}.staging"
    config_final = os.path.join(
        plugin_directory,
        f"{plan.target_plugin_name}{PLUGIN_CONFIG_FILE_SUFFIX}",
    )
    config_staging = f"{config_final}.clone-{task_id}.staging"
    package_artifact = await repository.record_artifact(
        task_id, "plugin_package", package_staging, plan.target_plugin_file
    )
    config_artifact = await repository.record_artifact(
        task_id, "configuration", config_staging, config_final
    )
    models_artifact: int | None = None
    models_staging: str | None = None
    if plan.clone_models and plan.source_models_path_exists and plan.target_models_path:
        models_staging = f"{plan.target_models_path}.clone-{task_id}.staging"
        models_artifact = await repository.record_artifact(
            task_id, "models", models_staging, plan.target_models_path
        )
    runtime_artifacts = await record_clone_runtime_artifacts(
        repository,
        task_id,
        plan.target_plugin_name,
    )
    await _run_publication(
        asyncio.to_thread(
            claim_staging_artifact_ownership,
            package_staging,
            task_id,
            "file",
        )
    )
    display_name = await clone_plugin_file(
        storage_manager=plugin_manager.dependencies.infrastructure.storage_manager,
        source_plugin_file=os.path.join(
            plugin_directory,
            f"{plan.source_plugin_name}{PLUGIN_FILE_SUFFIX}",
        ),
        target_plugin_file=package_staging,
        target_plugin_name=plan.target_plugin_name,
        aggregate_reservation=storage_reservation.lease,
        expected_required_bytes=storage_reservation.package_bytes,
        expected_source_digest=storage_reservation.package_source_digest,
    )
    await _run_publication(
        asyncio.to_thread(
            record_staging_artifact_ownership,
            package_staging,
            task_id,
            "file",
        )
    )
    await _require_artifact_transition(
        repository, task_id, package_artifact, "intended", "materialized"
    )
    if models_artifact is not None and models_staging and plan.source_models_path:
        await _run_publication(
            asyncio.to_thread(
                claim_staging_artifact_ownership,
                models_staging,
                task_id,
                "directory",
            )
        )
        await copy_directory_with_progress(
            plugin_manager,
            plan.source_models_path,
            models_staging,
            reply_channel,
            15,
            80,
            "Copying models",
            task_id=task_id,
            aggregate_reservation=storage_reservation.lease,
            expected_required_bytes=storage_reservation.models_bytes,
            expected_source_digest=storage_reservation.models_source_digest,
        )
        await ensure_correct_permissions(models_staging)
        await _run_publication(
            asyncio.to_thread(
                record_staging_artifact_ownership,
                models_staging,
                task_id,
                "directory",
            )
        )
        await _require_artifact_transition(
            repository, task_id, models_artifact, "intended", "materialized"
        )
    else:
        await progress_callback(80, "Models cloning skipped or no models directory found.")
    adjusted_config, adjusted = retarget_cloned_model_paths(
        plugin_manager,
        cloned_config,
        plan.source_plugin_name,
        plan.target_plugin_name,
        plan.source_models_path,
        plan.target_models_path if plan.clone_models else None,
    )
    if adjusted:
        cloned_config = adjusted_config
    await _run_publication(
        asyncio.to_thread(
            claim_staging_artifact_ownership,
            config_staging,
            task_id,
            "file",
        )
    )
    await plugin_manager.dependencies.infrastructure.config_manager.stage_config(
        config_staging,
        cloned_config,
        storage_reservation.lease,
        storage_reservation.config_bytes,
    )
    await ensure_correct_permissions(config_staging)
    await _run_publication(
        asyncio.to_thread(
            record_staging_artifact_ownership,
            config_staging,
            task_id,
            "file",
        )
    )
    await _require_artifact_transition(
        repository, task_id, config_artifact, "intended", "materialized"
    )
    async with (
        plugin_manager.dependencies.infrastructure.config_manager.plugin_config_mutation_scope(
            plan.target_plugin_name
        )
    ):
        await _require_phase_transition(repository, task_id, "staging", "staged")
        await _require_phase_transition(repository, task_id, "staged", "publishing")
        await _run_publication(
            asyncio.to_thread(
                publish_file_no_clobber,
                config_staging,
                config_final,
                task_id,
            )
        )
        await _require_artifact_transition(
            repository, task_id, config_artifact, "materialized", "published"
        )
        if models_artifact is not None and models_staging and plan.target_models_path:
            await _run_publication(
                asyncio.to_thread(
                    claim_directory_publication,
                    models_staging,
                    plan.target_models_path,
                    task_id,
                )
            )
            await _require_artifact_transition(
                repository, task_id, models_artifact, "materialized", "published"
            )
        await _run_publication(
            asyncio.to_thread(
                publish_file_no_clobber,
                package_staging,
                plan.target_plugin_file,
                task_id,
            )
        )
        await _require_artifact_transition(
            repository, task_id, package_artifact, "materialized", "published"
        )
        await _require_phase_transition(repository, task_id, "publishing", "registering")
        await progress_callback(88, "Loading cloned plugin...")
        activation_outcome = await prepare_clone_activation(
            plugin_manager,
            plan.target_plugin_name,
        )
        for artifact_id in runtime_artifacts:
            await _require_artifact_transition(
                repository, task_id, artifact_id, "intended", "materialized"
            )
        message = await commit_clone_activation(
            plugin_manager,
            plan=plan,
            task_id=task_id,
            fencing_token=fencing_token,
            display_name=display_name,
            outcome=activation_outcome,
            context=context,
        )
    return message
