"""SoAI - Shared MCP persistence dependencies [backend/mcp/shared_persistence_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.automation.protocols_database import (
    DatabaseAutomationRunsProtocol,
    DatabaseAutomationsProtocol,
)
from core.conversations.protocols_database_defaults import (
    DatabaseChatIdentityDefaultsProtocol,
    DatabaseChatModelDefaultsProtocol,
)
from core.di.validation import require_dependencies
from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
from core.tool_calls.protocols import DatabaseToolCallsProtocol

__all__ = ("MCPSharedPersistence",)


@dataclass(frozen=True, slots=True)
class MCPSharedPersistence:
    database_automations: DatabaseAutomationsProtocol
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol
    database_automation_runs: DatabaseAutomationRunsProtocol
    database_tool_calls: DatabaseToolCallsProtocol
    database_read_video: DatabaseReadVideoJobsProtocol

    def validate_shared_persistence(self, owner: str) -> None:
        require_dependencies(
            owner=owner,
            database_automation_runs=self.database_automation_runs,
            database_automations=self.database_automations,
            database_chat_identity_defaults=self.database_chat_identity_defaults,
            database_chat_model_defaults=self.database_chat_model_defaults,
            database_tool_calls=self.database_tool_calls,
            database_read_video=self.database_read_video,
        )
