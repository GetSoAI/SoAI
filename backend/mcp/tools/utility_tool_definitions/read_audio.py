"""SoAI - MCP utility tool definition: read_audio [backend/mcp/tools/utility_tool_definitions/read_audio.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_AUDIO

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_read_audio_tool_definitions",)


def build_read_audio_tool_definitions() -> dict[str, JSONDict]:
    return {
        "read_audio": {
            "title": "Read Audio",
            "description": (
                "Read audio for model analysis with a local speech-to-text model provided by "
                "an installed plugin, plus local file metadata. Returns transcript text, timing, "
                "source/container metadata, speech pacing, silence gaps, and speech model "
                "confidence diagnostics when the model reports them. If speech-to-text is not "
                "set up, the error explains which plugin backend or model to install."
            ),
            "icons": [build_tool_icon_entry(ICON_AUDIO)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": (
                            "ID of an uploaded file from /v1/files endpoint "
                            "(e.g., 'file-abc123')"
                        ),
                    },
                    "file_path": {
                        "type": "string",
                        "description": (
                            "Path to the audio file under workspace_path "
                            "(or an absolute path within it)."
                        ),
                    },
                    "model": {
                        "type": "string",
                        "description": (
                            "Local speech-to-text model. Omit to use the speech model setting. "
                            "Accepts 'auto' (first installed local model), a Whisper size "
                            "(tiny, base, small, medium, large, large-v2, large-v3), or an "
                            "installed model ID."
                        ),
                    },
                    "language": {
                        "type": "string",
                        "description": (
                            "Language code (e.g., 'en', 'es', 'fr'). "
                            "Auto-detected if not specified."
                        ),
                    },
                    "task": {
                        "type": "string",
                        "description": "Task to perform (default: transcribe)",
                        "enum": ["transcribe", "translate"],
                    },
                    "include_word_timestamps": {
                        "type": "boolean",
                        "description": (
                            "Include word-level timestamps and probabilities when the speech "
                            "model provides them (default: false)."
                        ),
                    },
                },
                "required": [],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source": {
                        "type": "object",
                        "description": "Resolved path, filename, extension, MIME type, and size.",
                    },
                    "container": {
                        "type": "object",
                        "description": (
                            "Local audio metadata such as duration, bitrate, sample rate, "
                            "channels, and tags when available."
                        ),
                    },
                    "request": {
                        "type": "object",
                        "description": "Model, task, language, and timestamp options used.",
                    },
                    "transcript": {
                        "type": "object",
                        "description": "Detected language, full text, duration, segments, and words.",
                    },
                    "speech_timeline": {
                        "type": "object",
                        "description": (
                            "Speech duration, silence duration, pause gaps, first/last speech, "
                            "and segment pacing."
                        ),
                    },
                    "content_stats": {
                        "type": "object",
                        "description": "Word, character, sentence, density, and pace statistics.",
                    },
                    "whisper_diagnostics": {
                        "type": "object",
                        "description": (
                            "Speech model confidence, no-speech, compression, temperature, and "
                            "per-segment diagnostic aggregates; values the model does not report "
                            "are null."
                        ),
                    },
                    "model_notes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Computed quality and interpretation notes for the model.",
                    },
                },
                "required": [
                    "source",
                    "container",
                    "request",
                    "transcript",
                    "speech_timeline",
                    "content_stats",
                    "whisper_diagnostics",
                    "model_notes",
                ],
            },
            "annotations": build_tool_annotation_flags(
                read_only=True,
                destructive=False,
                idempotent=True,
                open_world=False,
            ),
        },
    }
