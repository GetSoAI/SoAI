"""SoAI - Model parameter mutation and validation service assembly [backend/app/composition/model_services_parameters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from app.composition.build_models_parameter_executors import (
    ParameterServiceHolder,
    build_parameter_delete_executor,
    build_parameter_mutation_executor,
    build_parameter_update_executor,
)
from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.config.protocols import ConfigProtocol
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.models.protocols import ParameterManagerProtocol
from core.models.protocols_database import DatabaseModelsProtocol
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)
from models.actions.service import ModelActionsService
from models.information.service import ModelInformationService
from models.mutation_effects import ModelMutationEffects
from models.parameters.cache import AsyncParameterCache
from models.parameters.mutation.dependencies import ParameterMutationServiceDependencies
from models.parameters.mutation.service import ParameterMutationService
from models.parameters.service import (
    ModelParameterService,
    ModelParameterServiceDependencies,
)

__all__ = ("build_parameter_services",)

LOGGER_NAME = "SoAI.app.composition.model_services_parameters"


def build_parameter_services(
    *,
    config: ConfigProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    task_registry: TaskRegistryProtocol,
    database_models: DatabaseModelsProtocol,
    parameter_manager: ParameterManagerProtocol,
    metrics_manager: MetricsManagerProtocol,
    parameter_cache: AsyncParameterCache,
    mutation_effects: ModelMutationEffects,
    model_record_locks: AsyncLockRegistryProtocol[str],
    model_actions_service: ModelActionsService,
    model_information_service: ModelInformationService,
    shutdown_event: asyncio.Event,
) -> tuple[ParameterMutationService, ModelParameterService]:
    parameter_service_holder = ParameterServiceHolder()
    parameter_update_executor = build_parameter_update_executor(parameter_service_holder)
    parameter_delete_executor = build_parameter_delete_executor(parameter_service_holder)
    parameter_mutation_executor = build_parameter_mutation_executor(parameter_service_holder)
    model_parameter_mutation_service = ParameterMutationService(
        ParameterMutationServiceDependencies(
            logger=get_logger(LOGGER_NAME),
            shutdown_event=shutdown_event,
            cancellation_binder=cancellation_binder,
            spawn_tracked_task=spawn_tracked_task,
            finalizer_tracker=finalizer_tracker,
            num_workers=config.get_int("MODELS.MANAGER.PARAMETERS.UPDATE_WORKERS"),
            update_queue_max_size=config.get_int("MODELS.MANAGER.PARAMETERS.UPDATE_QUEUE_MAX_SIZE"),
            update_executor=parameter_update_executor,
            delete_executor=parameter_delete_executor,
            mutation_executor=parameter_mutation_executor,
            task_registry=task_registry,
        ),
    )
    model_parameter_service = ModelParameterService(
        ModelParameterServiceDependencies(
            database_models=database_models,
            param_manager=parameter_manager,
            parameter_mutation_service=model_parameter_mutation_service,
            parameter_cache=parameter_cache,
            model_record_locks=model_record_locks,
            mutation_effects=mutation_effects,
            metrics=metrics_manager,
            model_get_info=model_information_service.model_get_info,
            model_validate_and_get_context=model_actions_service.model_validate_and_get_context,
        ),
    )
    parameter_service_holder.service = model_parameter_service
    return model_parameter_mutation_service, model_parameter_service
