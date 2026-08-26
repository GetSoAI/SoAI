"""SoAI - Scheduler model eligibility evaluation for planning [backend/orchestrator/scheduling/model_eligibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal

from core.logging.trace import get_logger
from core.models.model_info_fields import coerce_plugin_name
from core.models.provider_backing import is_provider_backed_model
from core.state.provider_backed_availability import (
    PROVIDER_BACKED_IGNORED_PLUGIN_STATES,
)
from core.state.state_transition_sets import ELIGIBILITY_PROHIBITIVE_STATES
from core.validation.boolean_coercion import coerce_bool_with_default
from orchestrator.scheduling.dependencies import SchedulerPlanningDependencies
from orchestrator.scheduling.plugin_requirements import (
    RequirementEvaluation,
    evaluate_model_requirements,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("ModelEligibilityEvaluator",)

LOGGER_NAME = "SoAI.orchestrator.scheduling.model_eligibility"


class ModelEligibilityEvaluator:
    def __init__(self, deps: SchedulerPlanningDependencies) -> None:
        self._deps = deps

    async def evaluate(
        self,
        universal_id: str,
        exclusions: set[str],
        requirements: Mapping[str, JSONValue] | None = None,
    ) -> tuple[
        Literal["eligible", "on_cooldown", "unavailable", "unsupported"],
        JSONDict | None,
        RequirementEvaluation | None,
    ]:
        logger = get_logger(LOGGER_NAME)
        if universal_id in exclusions:
            return ("unavailable", None, None)
        model_info = await self._deps.model_information_service.model_get_info(universal_id)
        if not model_info:
            return ("unavailable", None, None)
        if not coerce_bool_with_default(model_info.get("is_enabled"), default=True, strict=True):
            await self._deps.queue.tracking.set_deferral_reason(
                universal_id,
                f"Model '{universal_id}' is disabled.",
            )
            return ("unavailable", None, None)
        status_value = model_info.get("status", "active")
        status = status_value if isinstance(status_value, str) else "active"
        if status != "active":
            return ("unavailable", None, None)
        plugin_name_value = coerce_plugin_name(model_info)
        if plugin_name_value is None:
            return ("unavailable", None, None)
        plugin_name = plugin_name_value
        raw_requirements = requirements or {}
        raw_capabilities = (
            raw_requirements.get("capabilities") if isinstance(raw_requirements, Mapping) else None
        )
        raw_modalities = (
            raw_requirements.get("modalities") if isinstance(raw_requirements, Mapping) else None
        )
        capabilities: tuple[str, ...] = (
            tuple(value for value in raw_capabilities if isinstance(value, str))
            if isinstance(raw_capabilities, list | tuple | set)
            else ()
        )
        modalities: tuple[str, ...] = (
            tuple(value for value in raw_modalities if isinstance(value, str))
            if isinstance(raw_modalities, list | tuple | set)
            else ()
        )
        evaluation: RequirementEvaluation | None = None
        if capabilities or modalities:
            evaluation = evaluate_model_requirements(
                model_info=model_info,
                capabilities=capabilities,
                modalities=modalities,
            )
            if not evaluation.meets:
                return ("unsupported", model_info, evaluation)
        if self._deps.transient_failures.is_on_cooldown(universal_id):
            await self._deps.queue.tracking.set_deferral_reason(
                universal_id,
                f"Model '{universal_id}' is on cooldown after repeated failures.",
            )
            return ("on_cooldown", model_info, evaluation)
        provider_backed = is_provider_backed_model(model_info)
        prohibitive_states = (
            ELIGIBILITY_PROHIBITIVE_STATES - PROVIDER_BACKED_IGNORED_PLUGIN_STATES
            if provider_backed
            else ELIGIBILITY_PROHIBITIVE_STATES
        )
        plugin_state = await self._deps.state_aggregator.get_plugin_status(plugin_name)
        if plugin_state in prohibitive_states:
            logger.debug(
                "Model [%s] is ineligible because its plugin '%s' is in a prohibitive state: %s",
                universal_id,
                plugin_name,
                plugin_state,
            )
            await self._deps.queue.tracking.set_deferral_reason(
                universal_id,
                f"Plugin '{plugin_name}' is temporarily unavailable (state: {plugin_state}).",
            )
            return ("on_cooldown", model_info, evaluation)
        if (
            not provider_backed
            and await self._deps.lifecycle.circuit_breakers.is_circuit_breaker_open(
                plugin_name,
            )
        ):
            logger.debug(
                "Model [%s] is ineligible because the circuit breaker for '%s' is open.",
                universal_id,
                plugin_name,
            )
            await self._deps.queue.tracking.set_deferral_reason(
                universal_id,
                f"Plugin '{plugin_name}' is temporarily unavailable (circuit breaker open).",
            )
            return ("on_cooldown", model_info, evaluation)
        logger.debug(
            "Model [%s] from plugin '%s' (state: %s) is eligible for planning.",
            universal_id,
            plugin_name,
            plugin_state,
        )
        return ("eligible", model_info, evaluation)
