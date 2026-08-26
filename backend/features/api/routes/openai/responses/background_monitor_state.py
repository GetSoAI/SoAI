"""SoAI - OpenAI Responses background monitor state [backend/features/api/routes/openai/responses/background_monitor_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("BackgroundResponsesState",)


@dataclass(slots=True)
class BackgroundResponsesState:
    response_id: str
    task_id: str
    user_id: int | None
    api_key_id: str | None
    model: str
    created_at: int
    event_sequence: int
    stream_enabled: bool
