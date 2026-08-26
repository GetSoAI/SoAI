"""SoAI - Assistant timeline terminal visible text reconciliation [backend/features/assistant_timeline/terminal_visible_text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("drain_terminal_visible_text",)


def drain_terminal_visible_text(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
) -> str:
    drained_visible_text = "".join(stream_transcript.drain_visible_text_deltas())
    transcript_text = stream_transcript.get_visible_text()
    projected_text = f"{runtime.assistant_visible_text}{drained_visible_text}"
    if transcript_text == projected_text:
        return drained_visible_text
    if transcript_text.startswith(runtime.assistant_visible_text):
        return transcript_text[len(runtime.assistant_visible_text) :]
    raise ValidationError(
        "Streaming assistant terminal visible text diverged from the persisted timeline.",
    )
