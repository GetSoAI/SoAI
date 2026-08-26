"""SoAI - Orchestrator model information resolution [backend/orchestrator/model_info_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.models.model_info_fields import resolve_plugin_name_from_model_info

if TYPE_CHECKING:
    from core.models.protocols import ModelInformationServiceProtocol
    from core.types.json import JSONDict

__all__ = (
    "ResolvedOrchestratorModel",
    "resolve_orchestrator_model",
)


@dataclass(frozen=True, slots=True)
class ResolvedOrchestratorModel:
    model_info: JSONDict
    plugin_name: str
    universal_id: str


async def resolve_orchestrator_model(
    model_information_service: ModelInformationServiceProtocol,
    universal_id: str,
    *,
    require_canonical_universal_id: bool,
) -> tuple[ResolvedOrchestratorModel | None, str | None]:
    model_info = await model_information_service.model_get_info(universal_id)
    plugin_name, error_reason = resolve_plugin_name_from_model_info(
        model_info,
        universal_id=universal_id,
    )
    if error_reason is not None:
        return (None, error_reason)
    if model_info is None or plugin_name is None:
        return (None, f"Model info for {universal_id} is invalid.")
    canonical_universal_id = universal_id
    canonical_universal_id_value = model_info.get("universal_id")
    if isinstance(canonical_universal_id_value, str) and canonical_universal_id_value:
        canonical_universal_id = canonical_universal_id_value
    elif require_canonical_universal_id:
        return (None, "Model info missing required universal_id during plugin queue dispatch.")
    return (
        ResolvedOrchestratorModel(
            model_info=model_info,
            plugin_name=plugin_name,
            universal_id=canonical_universal_id,
        ),
        None,
    )
