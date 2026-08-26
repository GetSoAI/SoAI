"""SoAI - Automation mutation result models [backend/core/automation/automation_mutation_results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "AutomationConversationVersion",
    "AutomationUpdateResult",
)


@dataclass(frozen=True, slots=True)
class AutomationConversationVersion:
    conv_id: str
    last_modified_at_ms: int


@dataclass(frozen=True, slots=True)
class AutomationUpdateResult:
    automation: JSONDict | None
    conversation_versions: tuple[AutomationConversationVersion, ...] = ()
    abandoned_run_ids: tuple[str, ...] = ()
    abandoned_owner_task_ids: tuple[str, ...] = ()
