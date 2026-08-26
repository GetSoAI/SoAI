"""SoAI - Virtual model candidate scoring for scheduler planning [backend/orchestrator/scheduling/virtual_model_candidate_scoring.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.models.model_info_fields import coerce_plugin_name
from core.models.provider_backing import is_provider_backed_model

if TYPE_CHECKING:
    from core.orchestrator.protocols_lifecycle import PluginStateProtocol
    from core.orchestrator.routing_config import ConstituentModelConfig
    from core.types.json import JSONDict
    from orchestrator.scheduling.dependencies import SchedulerPlanningDependencies

__all__ = (
    "EligibleVirtualModelCandidate",
    "order_load_balanced_virtual_model_candidates",
)


@dataclass(frozen=True, slots=True)
class EligibleVirtualModelCandidate:
    model_config: ConstituentModelConfig
    model_info: JSONDict
    original_index: int


@dataclass(frozen=True, slots=True)
class _CandidateScore:
    candidate: EligibleVirtualModelCandidate
    member_pressure: float
    plugin_pressure: float
    churn_rank: int


async def order_load_balanced_virtual_model_candidates(
    deps: SchedulerPlanningDependencies,
    virtual_model_name: str,
    candidates: list[EligibleVirtualModelCandidate],
) -> list[ConstituentModelConfig]:
    if len(candidates) <= 1:
        return [candidate.model_config for candidate in candidates]
    plugin_names_by_index = _resolve_candidate_plugin_names(candidates)
    plugin_names = set(plugin_names_by_index.values())
    plugin_state_snapshot, queue_sizes = await asyncio.gather(
        deps.lifecycle.watchers.get_plugin_states_snapshot(plugin_names),
        deps.capacity.get_queue_sizes(list(plugin_names)),
        return_exceptions=False,
    )
    reservation_counts = await deps.queue.execution_reservations.snapshot(
        [candidate.model_config.universal_id for candidate in candidates],
    )
    scores = [
        _score_candidate(
            deps,
            candidate,
            plugin_names_by_index[candidate.original_index],
            plugin_state_snapshot.get(plugin_names_by_index[candidate.original_index]),
            queue_sizes,
            reservation_counts,
        )
        for candidate in candidates
    ]
    ordered_scores = sorted(
        scores,
        key=lambda score: (
            score.member_pressure,
            score.plugin_pressure,
            score.churn_rank,
            score.candidate.original_index,
        ),
    )
    ordered_scores = await _rotate_leading_equal_score_group(
        deps,
        virtual_model_name,
        ordered_scores,
    )
    return [score.candidate.model_config for score in ordered_scores]


def _resolve_candidate_plugin_names(
    candidates: list[EligibleVirtualModelCandidate],
) -> dict[int, str]:
    plugin_names: dict[int, str] = {}
    for candidate in candidates:
        plugin_name = coerce_plugin_name(candidate.model_info)
        if plugin_name is None:
            raise StateError("Eligible virtual model candidate is missing plugin name.")
        plugin_names[candidate.original_index] = plugin_name
    return plugin_names


def _score_candidate(
    deps: SchedulerPlanningDependencies,
    candidate: EligibleVirtualModelCandidate,
    plugin_name: str,
    state: PluginStateProtocol | None,
    queue_sizes: dict[str, int],
    reservation_counts: dict[str, int],
) -> _CandidateScore:
    active_tasks = state.active_tasks if state is not None else ()
    avg_time = state.avg_processing_time_ema if state is not None else 1.0
    effective_limit = _effective_plugin_limit(deps, plugin_name)
    queued_count = queue_sizes.get(plugin_name, 0)
    active_count = len(active_tasks)
    reservation_count = reservation_counts.get(candidate.model_config.universal_id, 0)
    return _CandidateScore(
        candidate=candidate,
        member_pressure=(reservation_count / effective_limit) * avg_time,
        plugin_pressure=((active_count + queued_count) / effective_limit) * avg_time,
        churn_rank=_resolve_churn_rank(
            candidate,
            state.loaded_model_universal_id if state else None,
        ),
    )


def _effective_plugin_limit(deps: SchedulerPlanningDependencies, plugin_name: str) -> int:
    limit = deps.capacity.get_plugin_limit(plugin_name)
    if limit is None or limit <= 0:
        return 1
    return limit


async def _rotate_leading_equal_score_group(
    deps: SchedulerPlanningDependencies,
    virtual_model_name: str,
    ordered_scores: list[_CandidateScore],
) -> list[_CandidateScore]:
    if len(ordered_scores) <= 1:
        return ordered_scores
    first = ordered_scores[0]
    leading_group: list[_CandidateScore] = []
    remainder_start = 0
    for index, score in enumerate(ordered_scores):
        if (
            score.member_pressure == first.member_pressure
            and score.plugin_pressure == first.plugin_pressure
            and score.churn_rank == first.churn_rank
        ):
            leading_group.append(score)
            remainder_start = index + 1
            continue
        break
    if len(leading_group) <= 1:
        return ordered_scores
    rotated_models = await deps.virtual_model_rotation.select_next_candidate(
        virtual_model_name,
        [score.candidate.model_config for score in leading_group],
    )
    scores_by_universal_id = {
        score.candidate.model_config.universal_id: score for score in leading_group
    }
    rotated_scores = [scores_by_universal_id[model.universal_id] for model in rotated_models]
    return rotated_scores + ordered_scores[remainder_start:]


def _resolve_churn_rank(
    candidate: EligibleVirtualModelCandidate,
    loaded_model_universal_id: str | None,
) -> int:
    if is_provider_backed_model(candidate.model_info):
        return 0
    if loaded_model_universal_id == candidate.model_config.universal_id:
        return 0
    if loaded_model_universal_id:
        return 2
    return 1
