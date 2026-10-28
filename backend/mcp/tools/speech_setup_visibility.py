"""SoAI - MCP speech-to-text setup guidance visibility [backend/mcp/tools/speech_setup_visibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.media.speech_errors import SpeechToTextUnavailableError, without_setup_candidates
from core.state.access import AccessAction
from mcp.tools.access_control import tool_user_has_action

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("scope_speech_setup_error", "with_scoped_speech_setup")


async def scope_speech_setup_error(
    utility_tools: MCPUtilityToolsProtocol,
    error: SpeechToTextUnavailableError,
) -> SpeechToTextUnavailableError:
    if await tool_user_has_action(utility_tools, action=AccessAction.PLUGIN_READ):
        return error
    return without_setup_candidates(error)


async def with_scoped_speech_setup[Result](
    utility_tools: MCPUtilityToolsProtocol,
    operation: Awaitable[Result],
) -> Result:
    try:
        return await operation
    except SpeechToTextUnavailableError as error:
        scoped = await scope_speech_setup_error(utility_tools, error)
        if scoped is error:
            raise
        raise scoped from error
