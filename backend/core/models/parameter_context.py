"""SoAI - Model parameter context helpers [backend/core/models/parameter_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, overload

from core.tasks.orchestration_context import build_startup_param_fingerprint

if TYPE_CHECKING:
    from core.models.protocols import ParameterManagerProtocol
    from core.tasks.orchestration_context import OrchestrationContext
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "classify_parameters_and_build_fingerprint",
    "extract_parameters",
    "resolve_context_effective_parameters",
    "resolve_context_startup_parameters",
)


@overload
def extract_parameters(
    parameter_snapshot: tuple[JSONDict, int] | None,
    *,
    default: Literal[True],
) -> tuple[JSONDict, int]: ...


@overload
def extract_parameters(
    parameter_snapshot: tuple[JSONDict, int] | None,
    *,
    default: bool = False,
) -> tuple[JSONDict | None, int | None]: ...


def extract_parameters(
    parameter_snapshot: tuple[JSONDict, int] | None,
    *,
    default: bool = False,
) -> tuple[JSONDict | None, int | None]:
    if parameter_snapshot:
        params, version = parameter_snapshot
        return (params or {}, version)
    if default:
        return ({}, 0)
    return (None, None)


def resolve_context_effective_parameters(context: OrchestrationContext) -> dict[str, JSONValue]:
    effective_parameters: dict[str, JSONValue] = {
        **context.startup_params,
        **context.inference_params,
    }
    if effective_parameters:
        return effective_parameters
    snapshot_params, _version = extract_parameters(context.parameter_snapshot, default=True)
    return snapshot_params if snapshot_params is not None else {}


def resolve_context_startup_parameters(context: OrchestrationContext) -> dict[str, JSONValue]:
    startup_parameters = context.startup_params
    if startup_parameters:
        return dict(startup_parameters)
    snapshot_params, _version = extract_parameters(context.parameter_snapshot, default=True)
    return snapshot_params if snapshot_params is not None else {}


async def classify_parameters_and_build_fingerprint(
    *,
    param_manager: ParameterManagerProtocol,
    plugin_name: str,
    parameter_values: JSONDict,
) -> tuple[dict[str, JSONValue], dict[str, JSONValue], str]:
    startup_params, inference_params = await param_manager.classify_parameters(
        plugin_name,
        parameter_values,
    )
    startup_param_fingerprint = build_startup_param_fingerprint(startup_params)
    return startup_params, inference_params, startup_param_fingerprint
