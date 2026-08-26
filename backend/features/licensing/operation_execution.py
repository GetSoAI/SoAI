"""SoAI - Durable licensing authority operation execution [backend/features/licensing/operation_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from uuid import uuid4

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import (
    ApiError,
    ConcurrencyError,
    PayloadTooLargeError,
    SecurityError,
    ServiceUnavailableError,
    StateError,
    ValidationError,
)
from core.licensing.machine_protocol import PreparedLicensingRequest
from core.licensing.operation_outcomes import ACTIONABLE_AUTHORITY_FAILURE_CODES
from core.licensing.protocols import LicensingRepositoryProtocol
from core.licensing.storage_records import LicensingOperationInsert
from core.timing.constants import BACKGROUND_TIMEOUT_SEC
from core.timing.durations import MILLISECONDS_PER_DAY, seconds_to_ms
from core.timing.retry_backoff import (
    compute_exponential_backoff_seconds,
    parse_retry_after_milliseconds,
)
from core.types.json import JSONValue
from features.licensing.machine_client import LicensingAuthorityOutcome, LicensingMachineClient


@dataclass(frozen=True, slots=True)
class LicensingAttemptResult:
    operation_id: str
    expected_state: str
    state: str
    outcome: LicensingAuthorityOutcome | None


@dataclass(frozen=True, slots=True)
class LicensingOperationBinding:
    edition: str
    licensed_product_scope: str
    instance_id: str
    deployment_id: str | None = None


@dataclass(frozen=True, slots=True)
class NewLicensingAttempt:
    operation_type: str
    prepared: PreparedLicensingRequest
    idempotency_key: str
    binding: LicensingOperationBinding
    now_ms: int
    deactivation_reason: str | None = None


async def execute_new_licensing_attempt(
    *,
    repository: LicensingRepositoryProtocol,
    client: LicensingMachineClient,
    attempt: NewLicensingAttempt,
) -> LicensingAttemptResult:
    operation_id = str(uuid4())
    await repository.create_operation(
        LicensingOperationInsert(
            operation_id=operation_id,
            operation_type=attempt.operation_type,
            idempotency_key=attempt.idempotency_key,
            request_digest=attempt.prepared.request_digest,
            request_nonce=attempt.prepared.request_nonce,
            canonical_request=None,
            edition=attempt.binding.edition,
            licensed_product_scope=attempt.binding.licensed_product_scope,
            instance_id=attempt.binding.instance_id,
            created_at_ms=attempt.now_ms,
            deployment_id=attempt.binding.deployment_id,
            deactivation_reason=attempt.deactivation_reason,
        )
    )
    if not await repository.claim_operation(operation_id, attempt.now_ms):
        raise StateError("Prepared licensing operation could not be claimed.")
    return await _send(
        repository,
        client,
        operation_id,
        attempt.operation_type,
        attempt.prepared.canonical_document,
        1,
        attempt.now_ms,
        expected_state="sending",
    )


async def execute_operation_reconciliation(
    *,
    repository: LicensingRepositoryProtocol,
    client: LicensingMachineClient,
    operation_id: str,
    operation_type: str,
    canonical_request: bytes,
    attempt_count: int,
    now_ms: int,
) -> LicensingAttemptResult:
    return await _send(
        repository,
        client,
        operation_id,
        operation_type,
        canonical_request,
        attempt_count + 1,
        now_ms,
        expected_state="reconciling",
        machine_operation="operation-reconciliation",
    )


async def _send(
    repository: LicensingRepositoryProtocol,
    client: LicensingMachineClient,
    operation_id: str,
    operation_type: str,
    canonical_request: bytes,
    attempt_count: int,
    now_ms: int,
    *,
    expected_state: str,
    machine_operation: str | None = None,
) -> LicensingAttemptResult:
    retry_at = now_ms + _retry_delay_milliseconds(attempt_count, None)
    authority_operation = operation_type if machine_operation is None else machine_operation
    try:
        outcome = await asyncio.wait_for(
            client.send(
                authority_operation,
                canonical_request,
                response_operation=operation_type,
            ),
            timeout=BACKGROUND_TIMEOUT_SEC,
        )
    except asyncio.CancelledError:
        await uncancel_then_cleanup(
            _transition_unknown(repository, operation_id, expected_state, now_ms, retry_at)
        )
        raise
    except TimeoutError:
        await _transition_unknown(repository, operation_id, expected_state, now_ms, retry_at)
        return LicensingAttemptResult(operation_id, expected_state, "outcome_unknown", None)
    except ServiceUnavailableError as exception:
        retry_after = exception.headers.get("Retry-After") if exception.headers else None
        retry_at = now_ms + _retry_delay_milliseconds(attempt_count, retry_after)
        await _transition_unknown(repository, operation_id, expected_state, now_ms, retry_at)
        return LicensingAttemptResult(operation_id, expected_state, "outcome_unknown", None)
    except ApiError as exception:
        await _terminalize_failure(
            repository,
            operation_id,
            expected_state,
            _authority_failure_code(exception),
            now_ms,
        )
        raise
    except (PayloadTooLargeError, SecurityError, ValidationError):
        await _terminalize_failure(
            repository, operation_id, expected_state, "invalid_contract", now_ms
        )
        raise
    return LicensingAttemptResult(operation_id, expected_state, "response", outcome)


async def _transition_unknown(
    repository: LicensingRepositoryProtocol,
    operation_id: str,
    expected_state: str,
    now_ms: int,
    retry_at_ms: int,
) -> None:
    await _require_transition(
        repository.transition_operation(
            operation_id,
            expected_state=expected_state,
            target_state="outcome_unknown",
            updated_at_ms=now_ms,
            next_retry_at_ms=retry_at_ms,
        )
    )


async def _terminalize_failure(
    repository: LicensingRepositoryProtocol,
    operation_id: str,
    expected_state: str,
    code: str,
    now_ms: int,
) -> None:
    await _require_transition(
        repository.transition_operation(
            operation_id,
            expected_state=expected_state,
            target_state="failed",
            terminal_code=code,
            updated_at_ms=now_ms,
        )
    )


async def _require_transition(transition: Awaitable[bool]) -> None:
    if not await transition:
        raise ConcurrencyError("Licensing operation changed before state transition.")


def _authority_failure_code(exception: ApiError) -> str:
    if exception.code in ACTIONABLE_AUTHORITY_FAILURE_CODES:
        return exception.code
    if exception.code in {"operation_not_found", "idempotency_conflict", "invalid_input"}:
        return exception.code
    return "authority_rejected"


def _retry_delay_milliseconds(attempt_count: int, retry_after: JSONValue) -> int:
    exponential_delay = seconds_to_ms(
        compute_exponential_backoff_seconds(
            max(0, attempt_count - 1),
            base_seconds=5.0,
            maximum_seconds=3_600.0,
            jitter_ratio=0.2,
        )
    )
    authority_delay = parse_retry_after_milliseconds(
        retry_after,
        default_milliseconds=0,
        maximum_milliseconds=MILLISECONDS_PER_DAY,
    )
    return max(exponential_delay, authority_delay)


__all__ = (
    "LicensingAttemptResult",
    "LicensingOperationBinding",
    "NewLicensingAttempt",
    "execute_new_licensing_attempt",
    "execute_operation_reconciliation",
)
