"""SoAI - Model mutation command types [backend/core/events/types_models_model_commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.events.types_base import ReplyableUserCommand, UserCommand
from core.runtime.request_context import RequestContext

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "DeleteModelAliasCommand",
    "DeleteModelParametersCommand",
    "ModelDeleteCommand",
    "ModelDownloadCommand",
    "ResetModelOpenAICapabilityOverridesCommand",
    "TriggerModelDiscoveryCommand",
    "UpdateModelAliasCommand",
    "UpdateModelEnabledCommand",
    "UpdateModelOpenAICapabilityOverrideCommand",
    "UpdateModelParametersCommand",
)


@dataclass(slots=True)
class TriggerModelDiscoveryCommand(UserCommand):
    plugins_to_scan: list[str] | None = None
    context: RequestContext | None = None
    wait_for_completion: bool = False


@dataclass(slots=True)
class ModelDownloadCommand(ReplyableUserCommand):
    plugin_name: str
    model_id: str
    quantization: str | None = None
    context: RequestContext | None = None


@dataclass(slots=True)
class ModelDeleteCommand(ReplyableUserCommand):
    universal_id: str
    context: RequestContext | None = None


@dataclass(slots=True)
class UpdateModelParametersCommand(ReplyableUserCommand):
    universal_id: str
    parameters: JSONDict
    context: RequestContext | None = None


@dataclass(slots=True)
class DeleteModelParametersCommand(ReplyableUserCommand):
    universal_id: str
    keys: list[str]
    context: RequestContext | None = None


@dataclass(slots=True)
class UpdateModelAliasCommand(ReplyableUserCommand):
    universal_id: str
    display_name: str
    description: str | None = None
    context: RequestContext | None = None


@dataclass(slots=True)
class DeleteModelAliasCommand(ReplyableUserCommand):
    universal_id: str
    context: RequestContext | None = None


@dataclass(slots=True)
class UpdateModelEnabledCommand(ReplyableUserCommand):
    universal_id: str
    enabled: bool
    context: RequestContext | None = None


@dataclass(slots=True)
class UpdateModelOpenAICapabilityOverrideCommand(ReplyableUserCommand):
    universal_id: str
    category: str
    token: str
    enabled: bool
    context: RequestContext | None = None


@dataclass(slots=True)
class ResetModelOpenAICapabilityOverridesCommand(ReplyableUserCommand):
    universal_id: str
    context: RequestContext | None = None
