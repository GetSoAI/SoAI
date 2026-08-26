"""SoAI - Automation domain constants [backend/core/automation/automation_constants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "AUTOMATION_ACTIVE_RUN_STATUSES",
    "AUTOMATION_AGENT_MODE_VALUES",
    "AUTOMATION_DEFAULT_MAX_RUN_MINUTES",
    "AUTOMATION_DEFAULT_MAX_TURNS",
    "AUTOMATION_DEFAULT_MAX_TURN_CHARS",
    "AUTOMATION_HARD_MAX_RUN_MINUTES",
    "AUTOMATION_HARD_MAX_TURNS",
    "AUTOMATION_HARD_MAX_TURN_CHARS",
    "AUTOMATION_MAX_CONCURRENT_RUNS",
    "AUTOMATION_OCCURRENCES_MAX_ITEMS",
    "AUTOMATION_PAYLOAD_FIELDS",
    "AUTOMATION_RECURRENCE_VALUES",
    "AUTOMATION_RESULT_EXCERPT_CHARS",
    "AUTOMATION_RUNS_DEFAULT_LIMIT",
    "AUTOMATION_RUNS_MAX_LIMIT",
    "AUTOMATION_RUN_STATUS_VALUES",
    "AUTOMATION_SCHEDULER_DEFAULT_DUE_BATCH_LIMIT",
    "AUTOMATION_SCHEDULER_DEFAULT_TICK_SECONDS",
    "AUTOMATION_TERMINAL_RUN_STATUSES",
    "AUTOMATION_TIMEOUT_REASON_PREFIX",
    "build_automation_recurrence_error_message",
)

AUTOMATION_DEFAULT_MAX_TURNS = 1
AUTOMATION_DEFAULT_MAX_TURN_CHARS = 20_000
AUTOMATION_HARD_MAX_TURNS = 1000
AUTOMATION_HARD_MAX_TURN_CHARS = 100_000
AUTOMATION_RESULT_EXCERPT_CHARS = 500
AUTOMATION_OCCURRENCES_MAX_ITEMS = 5_000
AUTOMATION_RUNS_DEFAULT_LIMIT = 200
AUTOMATION_RUNS_MAX_LIMIT = 2_000
AUTOMATION_SCHEDULER_DEFAULT_TICK_SECONDS = 10.0
AUTOMATION_SCHEDULER_DEFAULT_DUE_BATCH_LIMIT = 100
AUTOMATION_MAX_CONCURRENT_RUNS = 2
AUTOMATION_DEFAULT_MAX_RUN_MINUTES = 30
AUTOMATION_HARD_MAX_RUN_MINUTES = 1440
AUTOMATION_TIMEOUT_REASON_PREFIX = "timeout:"

AUTOMATION_RECURRENCE_VALUES: tuple[str, ...] = (
    "none",
    "hourly",
    "daily",
    "weekly",
    "monthly",
    "yearly",
)


def build_automation_recurrence_error_message() -> str:
    return f"Automation recurrence must be one of: {', '.join(AUTOMATION_RECURRENCE_VALUES)}."


AUTOMATION_RUN_STATUS_VALUES: tuple[str, ...] = (
    "queued",
    "running",
    "completed",
    "error",
    "cancelled",
    "abandoned",
)
AUTOMATION_ACTIVE_RUN_STATUSES: tuple[str, ...] = ("queued", "running")
AUTOMATION_TERMINAL_RUN_STATUSES: tuple[str, ...] = (
    "completed",
    "error",
    "cancelled",
    "abandoned",
)
AUTOMATION_AGENT_MODE_VALUES: tuple[str, ...] = ("chat", "plan", "execute")

AUTOMATION_PAYLOAD_FIELDS: tuple[str, ...] = (
    "title",
    "enabled",
    "color",
    "timezone",
    "start_local",
    "recurrence",
    "turns",
    "max_turns",
    "max_turn_chars",
    "max_run_minutes",
    "interactive_tool_approval",
    "model_settings",
)
