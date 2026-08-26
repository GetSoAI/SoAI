"""SoAI - Agentic request message source contract [backend/features/agent/runtime/request_message_source.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.types.json_value import copy_json_dict_list

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("AgenticRequestMessageSource",)


@dataclass(frozen=True, slots=True)
class AgenticRequestMessageSource:
    canonical_messages: list[JSONDict]
    provider_projector: Callable[[list[JSONDict]], Awaitable[list[JSONDict]]] | None = None

    async def build_provider_messages(
        self,
        boundary_applied_messages: list[JSONDict],
    ) -> list[JSONDict]:
        source_messages = copy_json_dict_list(boundary_applied_messages)
        if self.provider_projector is None:
            return source_messages
        projected_messages = await self.provider_projector(source_messages)
        return copy_json_dict_list(projected_messages)
