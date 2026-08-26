"""SoAI - Model parameter mutation executor builders [backend/app/composition/build_models_parameter_executors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from models.parameters.mutation_ordering import MutationCallable
    from models.parameters.service import ModelParameterService

__all__ = (
    "ParameterServiceHolder",
    "build_parameter_delete_executor",
    "build_parameter_mutation_executor",
    "build_parameter_update_executor",
)


@dataclass(slots=True)
class ParameterServiceHolder:
    service: ModelParameterService | None = None


def build_parameter_update_executor(
    holder: ParameterServiceHolder,
) -> Callable[[str, JSONDict, int | None], Awaitable[None]]:
    async def parameter_update_executor(
        universal_id: str,
        parameters: JSONDict,
        order: int | None = None,
    ) -> None:
        service = holder.service
        if service is None:
            raise StateError("Parameter service not initialized")
        await service.model_execute_update_parameters(universal_id, parameters, order)

    return parameter_update_executor


def build_parameter_delete_executor(
    holder: ParameterServiceHolder,
) -> Callable[[str, list[str], int | None], Awaitable[None]]:
    async def parameter_delete_executor(
        universal_id: str,
        keys: list[str],
        order: int | None = None,
    ) -> None:
        service = holder.service
        if service is None:
            raise StateError("Parameter service not initialized")
        await service.model_execute_delete_parameters(universal_id, keys, order)

    return parameter_delete_executor


def build_parameter_mutation_executor(
    holder: ParameterServiceHolder,
) -> Callable[[str, str, int | None, MutationCallable], Awaitable[None]]:
    async def parameter_mutation_executor(
        universal_id: str,
        metric_key: str,
        metric_value: int | None,
        mutation: MutationCallable,
    ) -> None:
        service = holder.service
        if service is None:
            raise StateError("Parameter service not initialized")
        await service.model_process_parameter_mutation(
            universal_id,
            metric_key,
            metric_value,
            mutation,
        )

    return parameter_mutation_executor
