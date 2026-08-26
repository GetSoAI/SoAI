"""SoAI - Messaging observability field contract [backend/core/messaging/observability_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal

    from core.conversations.conversation_source import MessagingPlatform

    type MessagingLogPhase = Literal["start", "progress", "complete"]
    type MessagingLogOutcome = Literal[
        "success",
        "failure",
        "retryable",
        "unknown",
        "rejected",
        "skipped",
        "cancelled",
        "superseded",
    ]

__all__ = (
    "MessagingLogFields",
    "render_messaging_log_fields",
    "resolve_messaging_log_outcome",
    "sanitize_messaging_log_token",
)

MESSAGING_LOG_TOKEN_MAX_LENGTH = 120


def sanitize_messaging_log_token(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._:/-]", ".", value.strip())
    if not normalized:
        return "unset"
    if len(normalized) <= MESSAGING_LOG_TOKEN_MAX_LENGTH:
        return normalized
    return normalized[:MESSAGING_LOG_TOKEN_MAX_LENGTH]


def resolve_messaging_log_outcome(value: str) -> MessagingLogOutcome:
    if value == "success":
        return "success"
    if value in ("failure", "failed"):
        return "failure"
    if value == "retryable":
        return "retryable"
    if value == "rejected":
        return "rejected"
    if value == "skipped":
        return "skipped"
    if value == "cancelled":
        return "cancelled"
    if value == "superseded":
        return "superseded"
    return "unknown"


@dataclass(frozen=True, slots=True)
class MessagingLogFields:
    operation: str
    platform: MessagingPlatform | None = None
    phase: MessagingLogPhase | None = None
    outcome: MessagingLogOutcome | None = None
    account_id: str | None = None
    revision: int | None = None
    lifecycle_generation: int | None = None
    connection_generation: int | None = None
    start_mode: str | None = None
    operation_code: int | None = None
    close_code: int | None = None
    dispatch_sequence: int | None = None
    classification: str | None = None
    remote_thread_type: str | None = None
    admission_status: str | None = None
    ownership_state: str | None = None
    health_code: str | None = None
    attempt: int | None = None
    budget_remaining: int | None = None
    max_concurrency: int | None = None
    elapsed_ms: int | None = None
    interval_ms: int | None = None
    outcome_detail: str | None = None
    failure_code: str | None = None
    provider_status: int | None = None
    provider_error_code: int | None = None
    retry_after_ms: int | None = None
    delivery_id: str | None = None
    chunk_ordinal: int | None = None
    event_count: int | None = None
    page_count: int | None = None
    body_bytes: int | None = None
    account_count: int | None = None
    skipped_count: int | None = None
    suppressed_count: int | None = None
    trace_id: str | None = None


def _append_text(rendered: list[str], key: str, value: str | None) -> None:
    if value is None:
        return
    rendered.append(f"{key}={sanitize_messaging_log_token(value)}")


def _append_number(rendered: list[str], key: str, value: int | None) -> None:
    if value is None:
        return
    rendered.append(f"{key}={int(value)}")


def render_messaging_log_fields(log_fields: MessagingLogFields) -> str:
    rendered: list[str] = []
    _append_text(rendered, "operation", log_fields.operation)
    _append_text(rendered, "platform", log_fields.platform)
    _append_text(rendered, "phase", log_fields.phase)
    _append_text(rendered, "outcome", log_fields.outcome)
    _append_text(rendered, "account_id", log_fields.account_id)
    _append_number(rendered, "revision", log_fields.revision)
    _append_number(rendered, "lifecycle_generation", log_fields.lifecycle_generation)
    _append_number(rendered, "connection_generation", log_fields.connection_generation)
    _append_text(rendered, "start_mode", log_fields.start_mode)
    _append_number(rendered, "operation_code", log_fields.operation_code)
    _append_number(rendered, "close_code", log_fields.close_code)
    _append_number(rendered, "dispatch_sequence", log_fields.dispatch_sequence)
    _append_text(rendered, "classification", log_fields.classification)
    _append_text(rendered, "remote_thread_type", log_fields.remote_thread_type)
    _append_text(rendered, "admission_status", log_fields.admission_status)
    _append_text(rendered, "ownership_state", log_fields.ownership_state)
    _append_text(rendered, "health_code", log_fields.health_code)
    _append_number(rendered, "attempt", log_fields.attempt)
    _append_number(rendered, "budget_remaining", log_fields.budget_remaining)
    _append_number(rendered, "max_concurrency", log_fields.max_concurrency)
    _append_number(rendered, "elapsed_ms", log_fields.elapsed_ms)
    _append_number(rendered, "interval_ms", log_fields.interval_ms)
    _append_text(rendered, "outcome_detail", log_fields.outcome_detail)
    _append_text(rendered, "failure_code", log_fields.failure_code)
    _append_number(rendered, "provider_status", log_fields.provider_status)
    _append_number(rendered, "provider_error_code", log_fields.provider_error_code)
    _append_number(rendered, "retry_after_ms", log_fields.retry_after_ms)
    _append_text(rendered, "delivery_id", log_fields.delivery_id)
    _append_number(rendered, "chunk_ordinal", log_fields.chunk_ordinal)
    _append_number(rendered, "event_count", log_fields.event_count)
    _append_number(rendered, "page_count", log_fields.page_count)
    _append_number(rendered, "body_bytes", log_fields.body_bytes)
    _append_number(rendered, "account_count", log_fields.account_count)
    _append_number(rendered, "skipped_count", log_fields.skipped_count)
    _append_number(rendered, "suppressed_count", log_fields.suppressed_count)
    _append_text(rendered, "trace_id", log_fields.trace_id)
    return " ".join(rendered)
