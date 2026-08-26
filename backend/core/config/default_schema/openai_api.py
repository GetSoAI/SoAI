"""SoAI - Default config schema: OpenAI API [backend/core/config/default_schema/openai_api.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.byte_sizes import mib_to_bytes

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_openai_api_defaults",)


def build_openai_api_defaults() -> ConfigDict:
    return {
        "OPENAI": {
            "DEFAULT_IMAGE_MODEL_DALLE": "",
            "DEFAULT_IMAGE_MODEL_GPT": "",
            "MAX_FILE_UPLOAD_MB": 250,
            "TOKEN_COUNTING": {"APPROXIMATE_SAFETY_RATIO": 0.85},
            "AGENTIC": {
                "COMPACTION": {
                    "CONTEXT_MARGIN_RATIO": 0.10,
                    "POST_COMPACT_MARGIN_RATIO": 0.35,
                    "RESERVED_OUTPUT_TOKENS": 2048,
                    "SUMMARY_MAX_TOKENS": 2048,
                },
                "MAX_OUTPUT_TOKENS": 32_768,
                "DEFAULT_CONTEXT_WINDOW_TOKENS": 65_536,
                "EMPTY_OUTPUT_MAX_RETRIES": 3,
                "EMPTY_OUTPUT_SILENT_MAX_RETRIES": 2,
                "TOOL_RESULT_PROMPT_MAX_CHARS": 20_000,
                "TOOL_RESULT_PROMPT_MAX_TOTAL_CHARS_PER_TOOL_BLOCK": 60_000,
                "TOOL_RESULT_PROMPT_MAX_DEPTH": 6,
                "TOOL_RESULT_PROMPT_MAX_ITEMS": 200,
                "TOOL_RESULT_PROMPT_MAX_KEYS": 200,
                "TOOL_RESULT_IMAGE_RELAY_MAX_ENCODED_CHARS": mib_to_bytes(128),
                "TOOL_RESULT_IMAGE_RELAY_MAX_PIXELS": 4_000_000,
            },
            "PROMPTS": {
                "SOAI_SYSTEM_PROMPT_MODE": "auto",
                "MESSAGE_COMPATIBILITY_MODE": "auto",
            },
            "RESPONSES": {
                "BACKGROUND_MONITOR_MAX_SEC": 3600.0,
            },
            "KEY_QUOTAS": {
                "DEFAULT_COMPLETION_RESERVATION_TOKENS": 512,
                "MAX_COMPLETION_RESERVATION_TOKENS": 32_768,
                "MIN_TOKEN_RESERVATION_UNITS": 1,
                "STREAMING_OVERAGE_TOKENS": 64,
                "MAX_HOURLY_WINDOW_HOURS": 720,
                "RESERVATION_TTL_SEC": 3600,
                "RECONCILE_INTERVAL_SEC": 60,
                "RECONCILE_BATCH_LIMIT": 200,
            },
            "RATE_LIMITING": {
                "ENABLED": False,
                "DEFAULT_LIMIT": "600/minute",
                "STREAM_LIMIT": "60/minute",
                "ROUTERS": {},
            },
            "SECURITY": {
                "AUTH_FAILURE_RATELIMIT": {
                    "WINDOW_SECONDS": 60,
                    "MAX_FAILURES": 5,
                },
                "KEY_EXPIRATION": {
                    "DEFAULT_TTL_DAYS": 90,
                    "ROTATION_REMINDER_DAYS": 75,
                },
            },
        },
    }
