"""SoAI - OpenAI API key quota reservation helpers [backend/features/api/runtime/openai_quota_reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.notifications.system_admin_alerts import create_openai_quota_admin_alert
from core.openai.request_options import extract_openai_bool_flag
from core.openai.token_accounting import count_prompt_occupancy_async
from core.quotas.token_reservation_payloads import TOKEN_QUOTA_MODE
from core.runtime.protocols import RequestProtocol
from core.system_api.request_paths import get_scope_path
from core.system_api.route_paths import ANTHROPIC_MESSAGES_PATH
from core.timing.epoch import epoch_ms
from features.api.openai.api_key_quota_http_responses import (
    build_insufficient_quota_response,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_payload_too_large
from features.api.runtime.openai_request_state import (
    resolve_openai_api_key_context_optional,
)
from features.api.runtime.quota_reservation_decisions import (
    parse_quota_reservation_decision,
)
from features.api.runtime.quota_reservation_finalization import (
    release_quota_reservation_required,
)
from features.api.runtime.token_quota_estimates import (
    build_quota_token_reservation_estimate,
    enrich_token_quota_reservation,
    estimate_completion_reservation_tokens,
)
from features.openai.token_counting_safety import (
    resolve_approximate_prompt_reservation_tokens,
)

if TYPE_CHECKING:
    from core.openai.token_accounting import PromptOccupancy
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.openai_context.internal_protocols import (
        OpenAIApiContextProtocol,
    )

__all__ = (
    "release_token_quota_reservation_if_present",
    "reserve_token_quota_for_task",
)

LOGGER_NAME = "SoAI.features.api.openai_quota_reservations"
OPERATION_FEATURES_API_RUNTIME_OPENAI_QUOTA_RESERVATIONS_NOTIFY_EXHAUSTED = (
    "features.api.runtime.openai_quota_reservations.notify_exhausted"
)


def _should_reserve_completion_tokens(path: str | None) -> bool:
    if path is None:
        return True
    if path.endswith("/chat/completions"):
        return True
    if path.endswith("/completions"):
        return True
    if path.endswith("/responses"):
        return True
    if path == ANTHROPIC_MESSAGES_PATH:
        return True
    if path.endswith("/audio/transcriptions"):
        return True
    return path.endswith("/audio/translations")


async def release_token_quota_reservation_if_present(
    api_context: OpenAIApiContextProtocol,
    key_id: str | None,
    reservation: JSONDict | None,
    *,
    trace_id: str | None,
    operation: str,
) -> None:
    if key_id is None or reservation is None:
        return
    await release_quota_reservation_required(
        database_api_keys=api_context.dependencies.webui_manager.database_api_keys,
        key_id=key_id,
        reservation=reservation,
        trace_id=trace_id,
        operation=operation,
    )


async def reserve_token_quota_for_task(
    request: RequestProtocol,
    api_context: ApiContext,
    request_json: dict[str, JSONValue],
    *,
    prompt_count: PromptOccupancy | None = None,
) -> tuple[str | None, JSONDict | None, JSONResponse | None, PromptOccupancy | None]:
    context = resolve_openai_api_key_context_optional(request)
    if context is None:
        return (None, None, None, prompt_count)
    key_id = context.key_id
    trace_id = context.trace_id
    database_api_keys = api_context.dependencies.webui_manager.database_api_keys
    quota_config = await database_api_keys.get_quota_config(key_id)
    mode_value = quota_config.get("mode")
    quota_mode = mode_value if isinstance(mode_value, str) else "none"
    if quota_mode != TOKEN_QUOTA_MODE:
        return (key_id, None, None, prompt_count)
    resolved_prompt_count = prompt_count
    if resolved_prompt_count is None:
        resolved_prompt_count = await count_prompt_occupancy_async(
            prompt_token_counter=api_context.dependencies.prompt_token_counter,
            request_payload=request_json,
        )
    if resolved_prompt_count.capped:
        raise_payload_too_large(
            request,
            "Prompt exceeds the supported token-counting limit.",
            error_type="prompt_token_count_limit_exceeded",
        )
    prompt = resolve_approximate_prompt_reservation_tokens(
        resolved_prompt_count,
        api_context.dependencies.config,
    )
    path = get_scope_path(request.scope) or None
    completion_tokens = 0
    if _should_reserve_completion_tokens(path):
        completion_tokens = estimate_completion_reservation_tokens(
            request_json,
            api_context.dependencies.config,
        )
    is_streaming = extract_openai_bool_flag(
        request_json,
        key="stream",
        default=False,
        trace_id=trace_id,
    )
    estimate = build_quota_token_reservation_estimate(
        api_context.dependencies.config,
        prompt_tokens=prompt,
        completion_tokens=completion_tokens,
        is_streaming=is_streaming,
    )
    estimate_units = int(estimate.estimate_units)
    now_ts = epoch_ms()
    reservation_result = await database_api_keys.reserve_quota_units_for_mode(
        key_id,
        TOKEN_QUOTA_MODE,
        estimate_units,
        now_ts,
    )
    decision = parse_quota_reservation_decision(reservation_result, now_ts_ms=now_ts)
    if not decision.allowed:
        await _notify_quota_exhausted_noncritical(
            api_context,
            key_id=key_id,
            window=decision.window,
            trace_id=trace_id,
        )
        response = build_insufficient_quota_response(
            trace_id=trace_id,
            window=decision.window,
            retry_at_ms=decision.retry_at_ms,
            now_ts_ms=now_ts,
            status=decision.status,
        )
        return (key_id, None, response, resolved_prompt_count)
    if decision.reservation is None:
        return (key_id, None, None, resolved_prompt_count)
    return (
        key_id,
        enrich_token_quota_reservation(decision.reservation, estimate=estimate),
        None,
        resolved_prompt_count,
    )


async def _notify_quota_exhausted_noncritical(
    api_context: ApiContext,
    *,
    key_id: str,
    window: str,
    trace_id: str | None,
) -> None:
    try:
        database_api_keys = api_context.dependencies.webui_manager.database_api_keys
        key_row = await database_api_keys.get_key_by_id(key_id)
        key_label = _resolve_api_key_label(key_row, key_id)
        await create_openai_quota_admin_alert(
            api_context.dependencies.database_notifications,
            key_id=key_id,
            key_label=key_label,
            window_label=window,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to create API key quota notification.",
            operation=OPERATION_FEATURES_API_RUNTIME_OPENAI_QUOTA_RESERVATIONS_NOTIFY_EXHAUSTED,
            trace_id=trace_id,
            details={"key_id": key_id, "window": window},
            level="warning",
        )


def _resolve_api_key_label(key_row: JSONDict | None, key_id: str) -> str:
    if key_row is not None:
        label_value = key_row.get("label")
        if isinstance(label_value, str) and label_value.strip():
            return label_value.strip()
        prefix_value = key_row.get("prefix")
        if isinstance(prefix_value, str) and prefix_value.strip():
            return f"API key {prefix_value.strip()}"
    return f"API key {key_id[-8:]}"
