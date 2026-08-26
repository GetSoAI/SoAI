"""SoAI - Billing and usage helpers for orchestrator executor [backend/orchestrator/execution/billing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.models.model_info_fields import coerce_plugin_name
from core.network.hosts import anonymize_ip
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.quotas.token_reservation_payloads import resolve_token_quota_reservation
from core.tasks.prompt_token_metadata import resolve_task_prompt_tokens
from core.tasks.task import Task
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "UsageRecordIdentity",
    "apply_prompt_tokens",
    "perform_billing_record",
    "requires_api_key_token_accounting",
    "resolve_prompt_tokens",
    "resolve_usage_record_identity",
    "sanitize_client_id",
)

LOGGER_NAME = "SoAI.orchestrator.execution.billing"


@dataclass(frozen=True, slots=True)
class UsageRecordIdentity:
    plugin_name: str
    model_id: str
    client_id: str


def requires_api_key_token_accounting(task: Task) -> bool:
    metadata = task.metadata
    if not isinstance(metadata, Mapping):
        return False
    api_key_id = metadata.get("api_key_id")
    if isinstance(api_key_id, str) and api_key_id:
        return True
    return resolve_token_quota_reservation(metadata.get("quota")) is not None


def sanitize_client_id(raw_client_id: JSONValue | None) -> str:
    if raw_client_id is None:
        return "unknown_client"
    if not isinstance(raw_client_id, str):
        try:
            raw_client_id = str(raw_client_id)
        except (TypeError, ValueError):
            return "invalid_client"
    sanitized = raw_client_id.strip()[:128]
    return sanitized or "unknown_client"


def perform_billing_record(
    *,
    queue: OrchestratorQueueProtocol,
    metrics: MetricsManagerProtocol,
    task: Task,
    model_info: JSONDict,
    tokens: int,
    plugin_name: str | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if tokens <= 0:
        return
    identity = resolve_usage_record_identity(
        queue=queue,
        task=task,
        model_info=model_info,
        missing_prefix="Billing",
        plugin_name=plugin_name,
    )
    if identity is None:
        return
    logger.info(
        "Recording %s tokens for billing: client='%s', plugin='%s', model='%s'",
        tokens,
        identity.client_id,
        identity.plugin_name,
        identity.model_id,
    )
    metrics.record_tokens_for_billing(
        plugin=identity.plugin_name,
        model_id=identity.model_id,
        client_id=identity.client_id,
        tokens=tokens,
    )


def resolve_usage_record_identity(
    *,
    queue: OrchestratorQueueProtocol,
    task: Task,
    model_info: JSONDict,
    missing_prefix: str,
    plugin_name: str | None = None,
) -> UsageRecordIdentity | None:
    logger = get_logger(LOGGER_NAME)
    plugin_value = model_info.get("plugin")
    resolved_plugin_name = plugin_name.strip() if isinstance(plugin_name, str) else None
    if not resolved_plugin_name:
        resolved_plugin_name = coerce_plugin_name(model_info)
    if resolved_plugin_name is None:
        logger.warning(
            "%s skipped due to invalid model_info.plugin: %s",
            missing_prefix,
            plugin_value,
        )
        return None
    universal_id_value = model_info.get("universal_id")
    if not isinstance(universal_id_value, str) or not universal_id_value:
        logger.warning(
            "%s skipped due to invalid model_info.universal_id: %s",
            missing_prefix,
            universal_id_value,
        )
        return None
    context = queue.require_orchestration_context(task)
    event = context.event
    request_context = event.context if event else None
    payload = event.payload if event else {}
    raw_client_id = payload.get("user")
    if not raw_client_id:
        raw_client_id = (
            anonymize_ip(request_context.client_ip)
            if request_context and request_context.client_ip
            else "unknown_ip"
        )
    return UsageRecordIdentity(
        plugin_name=resolved_plugin_name,
        model_id=universal_id_value,
        client_id=sanitize_client_id(raw_client_id),
    )


def resolve_prompt_tokens(task: Task) -> int | None:
    return resolve_task_prompt_tokens(task)


def apply_prompt_tokens(task: Task, usage: JSONDict) -> JSONDict:
    prompt_tokens_from_usage = coerce_optional_non_negative_int_strict(usage.get("prompt_tokens"))
    prompt_tokens_from_task = resolve_prompt_tokens(task)
    resolved_prompt_tokens = prompt_tokens_from_usage
    if resolved_prompt_tokens is None and prompt_tokens_from_task is not None:
        resolved_prompt_tokens = prompt_tokens_from_task
        usage["prompt_tokens"] = prompt_tokens_from_task
    completion_tokens = coerce_optional_non_negative_int_strict(usage.get("completion_tokens"))
    total_tokens = coerce_optional_non_negative_int_strict(usage.get("total_tokens"))
    if (
        completion_tokens is not None
        and resolved_prompt_tokens is not None
        and (total_tokens is None or total_tokens < resolved_prompt_tokens + completion_tokens)
    ):
        usage["total_tokens"] = resolved_prompt_tokens + completion_tokens
    return usage
