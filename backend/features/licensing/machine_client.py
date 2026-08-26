"""SoAI - Bounded licensing authority client [backend/features/licensing/machine_client.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Never

import httpx2

from core.errors.exceptions import (
    ApiError,
    PayloadTooLargeError,
    SecurityError,
    ServiceUnavailableError,
    ValidationError,
)
from core.licensing.canonicalization import canonicalize_licensing_json
from core.serialization.json_parsing import parse_json_value
from core.timing.retry_backoff import parse_retry_after_seconds
from core.types.json import JSONDict
from core.validation.object_fields import require_exact_json_fields
from core.validation.record_fields import require_json_object

__all__ = (
    "LicensingAuthorityOutcome",
    "LicensingMachineClient",
    "MAX_AUTHORITY_RESPONSE_BYTES",
    "WHOLE_ATTEMPT_TIMEOUT_SECONDS",
)

MAX_AUTHORITY_RESPONSE_BYTES = 64 * 1024
WHOLE_ATTEMPT_TIMEOUT_SECONDS = 30.0
_REDIRECTS = frozenset((301, 302, 303, 307, 308))
_RETRYABLE_STATUS = frozenset((429, 500, 502, 503, 504))


def _authority_operation_path(operation: str) -> str:
    path = {
        "evaluation": "/api/v1/licensing/evaluations",
        "os-evaluation-conversion": "/api/v1/licensing/os-evaluation-conversions",
        "os-evaluation-reversion": "/api/v1/licensing/os-evaluation-reversions",
        "activation": "/api/v1/licensing/activations",
        "commercial-conversion": "/api/v1/licensing/commercial-conversions",
        "deployment-reclassification": "/api/v1/licensing/deployment-reclassifications",
        "term-renewal": "/api/v1/licensing/term-renewals",
        "operation-reconciliation": "/api/v1/licensing/operation-reconciliations",
        "deactivation": "/api/v1/licensing/deactivations",
    }.get(operation)
    if path is None:
        raise ValidationError("Licensing authority operation is invalid.")
    return path


def _authority_request_timeout() -> httpx2.Timeout:
    return httpx2.Timeout(connect=5.0, pool=5.0, write=10.0, read=20.0)


@dataclass(frozen=True, slots=True)
class LicensingAuthorityOutcome:
    state: str
    fields: JSONDict
    signed_document: bytes | None
    document_type: str | None


class LicensingMachineClient:
    def __init__(self, http_client: httpx2.AsyncClient, authority_origin: str) -> None:
        if authority_origin != "https://soai.to":
            raise SecurityError("Licensing authority origin is not approved.")
        self._http_client = http_client
        self._authority_origin = authority_origin

    async def send(
        self,
        operation: str,
        canonical_request: bytes,
        *,
        response_operation: str | None = None,
    ) -> LicensingAuthorityOutcome:
        path = _authority_operation_path(operation)
        if len(canonical_request) > 16 * 1024:
            raise PayloadTooLargeError("Licensing authority request exceeds its V1 limit.")
        headers = {
            "Accept": "application/json",
            "Cache-Control": "no-store",
            "Content-Type": "application/json",
        }
        try:
            async with asyncio.timeout(WHOLE_ATTEMPT_TIMEOUT_SECONDS):
                async with self._http_client.stream(
                    "POST",
                    self._authority_origin + path,
                    content=canonical_request,
                    headers=headers,
                    timeout=_authority_request_timeout(),
                    follow_redirects=False,
                ) as response:
                    _validate_response_headers(response)
                    if response.status_code in _RETRYABLE_STATUS:
                        _raise_retryable(response)
                    raw_response = await _read_bounded_response(response)
                    return _decode_response(
                        operation if response_operation is None else response_operation,
                        response,
                        raw_response,
                    )
        except TimeoutError as exception:
            raise ServiceUnavailableError("Licensing authority request timed out.") from exception
        except httpx2.TimeoutException as exception:
            raise ServiceUnavailableError("Licensing authority request timed out.") from exception
        except httpx2.RequestError as exception:
            raise ServiceUnavailableError("Licensing authority is unreachable.") from exception


async def _read_bounded_response(response: httpx2.Response) -> bytes:
    declared_length = response.headers.get("content-length")
    if declared_length is not None:
        try:
            parsed_length = int(declared_length)
            if parsed_length < 0:
                raise ValidationError("Licensing authority content length is invalid.")
            if parsed_length > MAX_AUTHORITY_RESPONSE_BYTES:
                raise PayloadTooLargeError("Licensing authority response exceeds its V1 limit.")
        except ValueError as exception:
            raise ValidationError("Licensing authority content length is invalid.") from exception
    content = bytearray()
    async for chunk in response.aiter_bytes():
        content.extend(chunk)
        if len(content) > MAX_AUTHORITY_RESPONSE_BYTES:
            raise PayloadTooLargeError("Licensing authority response exceeds its V1 limit.")
    return bytes(content)


def _decode_response(
    operation: str,
    response: httpx2.Response,
    raw_response: bytes,
) -> LicensingAuthorityOutcome:
    parsed = parse_json_value(
        raw_response,
        field="licensing authority response",
        max_depth=12,
        strict_utf8=True,
        reject_duplicate_keys=True,
    )
    payload = require_json_object(
        parsed,
        label="Licensing authority response",
        build_error=ValidationError,
        invalid_message="Licensing authority response must be an object.",
    )
    if 200 <= response.status_code < 300:
        return _decode_success(operation, payload)
    _raise_safe_error(response.status_code, payload)
    raise ValidationError("Licensing authority error projection returned unexpectedly.")


def _validate_response_headers(response: httpx2.Response) -> None:
    if response.status_code in _REDIRECTS:
        raise SecurityError("Licensing authority redirect is not permitted.")
    if (
        response.status_code not in _RETRYABLE_STATUS
        and _response_media_type(response) != "application/json"
    ):
        raise ValidationError("Licensing authority response must be application/json.")


def _response_media_type(response: httpx2.Response) -> str:
    content_type = response.headers.get("content-type", "")
    if not isinstance(content_type, str):
        raise ValidationError("Licensing authority content type is invalid.")
    return content_type.split(";", 1)[0].strip().lower()


def _raise_retryable(response: httpx2.Response) -> Never:
    retry_after = min(
        86_400,
        parse_retry_after_seconds(response.headers.get("retry-after")),
    )
    headers = {"Retry-After": str(retry_after)} if retry_after > 0 else None
    raise ServiceUnavailableError(
        "Licensing authority is temporarily unavailable.",
        headers=headers,
    )


def _decode_success(operation: str, payload: JSONDict) -> LicensingAuthorityOutcome:
    if payload.get("schema_version") != 1:
        raise ValidationError("Licensing authority response schema is invalid.")
    state = payload.get("state")
    if not isinstance(state, str):
        raise ValidationError("Licensing authority response state is invalid.")
    if operation == "evaluation" and state == "evaluation_pending":
        fields = frozenset(("schema_version", "state", "evaluation_id", "pending_expires_at_ms"))
        signed_document = None
        document_type = None
    elif operation in {"activation", "os-evaluation-conversion"} and state == "evaluation_active":
        fields = frozenset(
            ("schema_version", "state", "evaluation_id", "deployment_id", "entitlement")
        )
        signed_document = _canonical_signed_document(payload, "entitlement", "entitlement")
        document_type = "entitlement"
    elif operation == "activation" and state == "activated":
        fields = frozenset(
            ("schema_version", "state", "activation_id", "deployment_id", "entitlement")
        )
        signed_document = _canonical_signed_document(payload, "entitlement", "entitlement")
        document_type = "entitlement"
    elif operation in {
        "os-evaluation-reversion",
        "commercial-conversion",
        "deployment-reclassification",
        "term-renewal",
    } and state in {
        "personal_active",
        "commercial_active",
        "commercial_continuity",
    }:
        fields = frozenset(("schema_version", "state", "deployment_id", "entitlement"))
        signed_document = _canonical_signed_document(payload, "entitlement", "entitlement")
        document_type = "entitlement"
    elif state in {"suspended", "terminated"}:
        fields = frozenset(("schema_version", "state", "deployment_id", "licensing_status"))
        signed_document = _canonical_signed_document(
            payload,
            "licensing_status",
            "licensing_status",
        )
        document_type = "licensing_status"
    elif operation == "deactivation" and state == "deactivated":
        fields = frozenset(("schema_version", "state", "deployment_id"))
        signed_document = None
        document_type = None
    else:
        raise ValidationError("Licensing authority response state is not valid for the operation.")
    require_exact_json_fields(payload, allowed_fields=fields, label="Licensing authority response")
    for field_name in fields - {
        "entitlement",
        "licensing_status",
        "schema_version",
        "pending_expires_at_ms",
    }:
        if field_name != "state" and not isinstance(payload.get(field_name), str):
            raise ValidationError("Licensing authority response identity is invalid.")
    pending_expiry = payload.get("pending_expires_at_ms")
    if pending_expiry is not None and (
        isinstance(pending_expiry, bool) or not isinstance(pending_expiry, int)
    ):
        raise ValidationError("Licensing authority pending expiry is invalid.")
    return LicensingAuthorityOutcome(state, payload, signed_document, document_type)


def _canonical_signed_document(
    payload: JSONDict,
    field: str,
    expected_document_type: str,
) -> bytes:
    document = payload.get(field)
    if not isinstance(document, dict):
        raise ValidationError("Licensing authority signed document is invalid.")
    signed_payload = document.get("payload")
    signature_domain = document.get("signature_domain")
    if not isinstance(signed_payload, dict) or not isinstance(signature_domain, str):
        raise ValidationError("Licensing authority signed document is invalid.")
    is_status = (
        signature_domain == "soai-licensing-status-v1"
        and signed_payload.get("document_type") == "licensing_status"
    )
    is_entitlement = (
        signature_domain
        in {
            "soai-entitlement-evaluation-v1",
            "soai-entitlement-commercial-term-v1",
            "soai-entitlement-commercial-continuity-v1",
            "soai-entitlement-personal-os-v1",
            "soai-deployment-binding-commercial-perpetual-v1",
        }
        and isinstance(signed_payload.get("entitlement_type"), str)
        and "document_type" not in signed_payload
    )
    actual_document_type = (
        "licensing_status" if is_status else "entitlement" if is_entitlement else None
    )
    if actual_document_type != expected_document_type:
        raise ValidationError("Licensing authority signed document type is invalid.")
    return canonicalize_licensing_json(document)


def _raise_safe_error(status_code: int, payload: JSONDict) -> None:
    code, trace_id = _validate_safe_error(payload)
    raise ApiError(
        "Licensing authority rejected the request.",
        code=code,
        http_status=status_code,
        trace_id=trace_id,
    )


def _validate_safe_error(payload: JSONDict) -> tuple[str, str]:
    require_exact_json_fields(payload, allowed_fields=("error",), label="Licensing authority error")
    error = require_json_object(
        payload.get("error"),
        label="Licensing authority error",
        build_error=ValidationError,
        invalid_message="Licensing authority error must be an object.",
    )
    require_exact_json_fields(
        error,
        allowed_fields=("code", "message", "trace_id"),
        label="Licensing authority error",
    )
    code = error.get("code")
    message = error.get("message")
    trace_id = error.get("trace_id")
    if not isinstance(code, str) or not code:
        raise ValidationError("Licensing authority error envelope is invalid.")
    if not isinstance(message, str) or not message:
        raise ValidationError("Licensing authority error envelope is invalid.")
    if not isinstance(trace_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{8,64}", trace_id) is None:
        raise ValidationError("Licensing authority error envelope is invalid.")
    return code, trace_id
