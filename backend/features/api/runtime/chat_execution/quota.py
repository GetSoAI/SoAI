"""SoAI - Conversation turn quota reservation [backend/features/api/runtime/chat_execution/quota.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.openai.request_field_filtering import build_inference_request_payload
from core.openai.token_accounting import count_prompt_occupancy_async
from core.openai.token_counter import PromptTokenCounter
from core.timing.epoch import epoch_ms
from features.api.runtime.quota_reservation_decisions import (
    parse_quota_reservation_decision,
)
from features.api.runtime.quota_reservation_finalization import (
    finalize_quota_reservation_required_for_api,
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
    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.config.protocols import ConfigProtocol
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "ConversationTurnQuotaDenied",
    "ConversationTurnQuotaReservation",
    "finalize_conversation_turn_request_quota",
    "reserve_conversation_turn_quota",
    "reserve_conversation_turn_stream_quota",
)

OPERATION_RESERVE_QUOTA = "chat.conversation_turn.reserve_quota"


@dataclass(frozen=True, slots=True)
class ConversationTurnQuotaReservation:
    key_id: str
    token_reservation: JSONDict | None


@dataclass(frozen=True, slots=True)
class ConversationTurnQuotaDenied:
    window: str
    retry_at_ms: int
    message: str


async def reserve_conversation_turn_stream_quota(
    *,
    api_dependencies: ApiDependencies,
    user_id: int,
    request_json: JSONDict,
    logger: LoggerProtocol,
) -> ConversationTurnQuotaDenied | ConversationTurnQuotaReservation | None:
    if user_id <= 0:
        return None
    try:
        return await reserve_conversation_turn_quota(
            database_api_keys=api_dependencies.database_api_keys,
            user_id=user_id,
            request_json=build_inference_request_payload(request_json),
            config=api_dependencies.config,
            prompt_token_counter=api_dependencies.prompt_token_counter,
        )
    except RECOVERABLE_EXCEPTIONS as quota_exception:
        coerced_quota = coerce_to_soai_error(
            quota_exception,
            operation=OPERATION_RESERVE_QUOTA,
        )
        log_exception(
            logger,
            coerced_quota,
            message="Failed to reserve conversation turn quota (blocking request).",
            operation=OPERATION_RESERVE_QUOTA,
            level="warning",
        )
        return ConversationTurnQuotaDenied(
            window="backend_error",
            retry_at_ms=epoch_ms(),
            message="Quota enforcement backend unavailable; request blocked.",
        )


async def reserve_conversation_turn_quota(
    database_api_keys: DatabaseAPIKeysProtocol,
    user_id: int,
    request_json: dict[str, JSONValue],
    config: ConfigProtocol,
    *,
    prompt_token_counter: PromptTokenCounter,
) -> ConversationTurnQuotaReservation | ConversationTurnQuotaDenied | None:
    key_id = await database_api_keys.get_active_key_id_for_user(user_id)
    if key_id is None:
        return None
    prompt_occupancy = await count_prompt_occupancy_async(
        prompt_token_counter=prompt_token_counter,
        request_payload=request_json,
    )
    if prompt_occupancy.capped:
        return ConversationTurnQuotaDenied(
            window="prompt_token_count_limit",
            retry_at_ms=epoch_ms(),
            message="Prompt exceeds the supported token-counting limit.",
        )
    now_ts = epoch_ms()
    request_result = await database_api_keys.reserve_quota_units_for_mode(
        key_id,
        "requests",
        1,
        now_ts,
        record_usage=True,
    )
    request_decision = parse_quota_reservation_decision(request_result, now_ts_ms=now_ts)
    if not request_decision.allowed:
        return ConversationTurnQuotaDenied(
            window=request_decision.window,
            retry_at_ms=request_decision.retry_at_ms,
            message=f"Quota exceeded for {request_decision.window}.",
        )
    request_reservation = request_decision.reservation
    if request_reservation is not None:
        await finalize_conversation_turn_request_quota(
            database_api_keys,
            key_id,
            request_reservation,
        )
    completion_tokens = estimate_completion_reservation_tokens(request_json, config)
    estimate = build_quota_token_reservation_estimate(
        config,
        prompt_tokens=resolve_approximate_prompt_reservation_tokens(
            prompt_occupancy,
            config,
        ),
        completion_tokens=completion_tokens,
        is_streaming=True,
    )
    token_result = await database_api_keys.reserve_quota_units_for_mode(
        key_id,
        "tokens",
        int(estimate.estimate_units),
        now_ts,
    )
    token_decision = parse_quota_reservation_decision(token_result, now_ts_ms=now_ts)
    if not token_decision.allowed:
        return ConversationTurnQuotaDenied(
            window=token_decision.window,
            retry_at_ms=token_decision.retry_at_ms,
            message=f"Quota exceeded for {token_decision.window}.",
        )
    token_reservation = token_decision.reservation
    if token_reservation is not None:
        token_reservation = enrich_token_quota_reservation(
            token_reservation,
            estimate=estimate,
        )
    return ConversationTurnQuotaReservation(
        key_id=key_id,
        token_reservation=token_reservation,
    )


async def finalize_conversation_turn_request_quota(
    database_api_keys: DatabaseAPIKeysProtocol,
    key_id: str,
    request_reservation: JSONDict,
) -> None:
    await finalize_quota_reservation_required_for_api(
        database_api_keys=database_api_keys,
        key_id=key_id,
        reservation=request_reservation,
        actual_units=1,
        trace_id=None,
        operation="conversation_turn_quota.finalize_request",
    )
