"""SoAI - Bounded SoAIBench website publication transport [backend/hardware/soaibench/publication_transport.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import re
from typing import Never

import httpx2

from core.errors.exceptions import ApiError, SoAIError, ValidationError
from core.network.redirect_headers import REDIRECT_STATUS_CODES
from core.runtime.network_policy import OfflineModeError
from core.serialization.json_parsing import parse_json_dict, parse_json_value
from core.timing.retry_backoff import parse_retry_after_seconds
from core.types.json import JSONDict
from hardware.soaibench.publication_receipt_validation import validate_publication_receipt

__all__ = ("PUBLICATION_URL", "exchange_soaibench_json", "publish_to_soaibench")

PUBLICATION_URL = "https://soai.to/api/v1/soaibench/submissions"
MAX_RESPONSE_BYTES = 16 * 1024
WHOLE_ATTEMPT_TIMEOUT_SECONDS = 14.0


async def publish_to_soaibench(
    http_client: httpx2.AsyncClient,
    canonical_submission: bytes,
    *,
    run_id: str,
    expected_score: int,
    installation_id: str,
) -> tuple[int, JSONDict]:
    headers = {
        "Accept": "application/json",
        "Cache-Control": "no-store",
        "Content-Type": "application/json; charset=utf-8",
        "Idempotency-Key": run_id,
        "X-SoAIBench-Installation-ID": installation_id,
    }
    request = http_client.build_request(
        "POST",
        PUBLICATION_URL,
        content=canonical_submission,
        headers=headers,
        timeout=httpx2.Timeout(connect=5.0, pool=5.0, write=10.0, read=20.0),
    )
    status_code, raw, details = await exchange_soaibench_json(
        http_client, request, accepted_statuses=frozenset((200, 201))
    )
    try:
        receipt = _validated_receipt_bytes(raw, expected_score)
        _validate_success_matrix(status_code, receipt)
    except ApiError as exception:
        exception.details = details
        raise
    return status_code, receipt


async def exchange_soaibench_json(
    http_client: httpx2.AsyncClient,
    request: httpx2.Request,
    *,
    accepted_statuses: frozenset[int],
) -> tuple[int, bytes, JSONDict | None]:
    for credential_header in ("authorization", "cookie", "proxy-authorization"):
        request.headers.pop(credential_header, None)
    try:
        async with asyncio.timeout(WHOLE_ATTEMPT_TIMEOUT_SECONDS):
            response = await http_client.send(
                request,
                stream=True,
                auth=None,
                follow_redirects=False,
            )
            try:
                details = _upstream_details(response)
                if response.status_code in REDIRECT_STATUS_CODES:
                    _raise(
                        "soaibench_publication_invalid_response",
                        "SoAIBench publication service returned a redirect.",
                        502,
                        details=details,
                    )
                raw = await _read_response(response)
                if response.status_code not in accepted_statuses:
                    if 200 <= response.status_code < 300:
                        _raise(
                            "soaibench_publication_invalid_response",
                            "SoAIBench publication service returned an invalid success status.",
                            502,
                            details=details,
                        )
                    _raise_upstream(response, raw, details)
                if not _is_json_content_type(response.headers.get("content-type")):
                    _raise(
                        "soaibench_publication_invalid_response",
                        "SoAIBench publication response content type is invalid.",
                        502,
                        details=details,
                    )
                return response.status_code, raw, details
            finally:
                await response.aclose()
    except OfflineModeError as exception:
        raise ApiError(
            "SoAIBench publication is unavailable while offline mode is enabled.",
            code="soaibench_publication_offline",
            http_status=503,
        ) from exception
    except TimeoutError as exception:
        raise ApiError(
            "SoAIBench publication timed out.",
            code="soaibench_publication_timeout",
            http_status=504,
        ) from exception
    except httpx2.TimeoutException as exception:
        raise ApiError(
            "SoAIBench publication timed out.",
            code="soaibench_publication_timeout",
            http_status=504,
        ) from exception
    except httpx2.RequestError as exception:
        raise ApiError(
            "SoAIBench publication service is unreachable.",
            code="soaibench_publication_unavailable",
            http_status=503,
        ) from exception


async def _read_response(response: httpx2.Response) -> bytes:
    declared = response.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) < 0 or int(declared) > MAX_RESPONSE_BYTES:
                raise ValueError
        except ValueError as exception:
            raise ApiError(
                "SoAIBench publication response is invalid.",
                code="soaibench_publication_invalid_response",
                http_status=502,
            ) from exception
    content = bytearray()
    async for chunk in response.aiter_bytes():
        content.extend(chunk)
        if len(content) > MAX_RESPONSE_BYTES:
            _raise(
                "soaibench_publication_invalid_response",
                "SoAIBench publication response is too large.",
                502,
            )
    return bytes(content)


def _validated_receipt_bytes(raw: bytes, expected_score: int) -> JSONDict:
    try:
        parsed = parse_json_value(
            raw,
            field="SoAIBench publication response",
            strict_utf8=True,
            reject_duplicate_keys=True,
        )
    except ValidationError as exception:
        raise ApiError(
            "SoAIBench publication response is invalid.",
            code="soaibench_publication_invalid_response",
            http_status=502,
        ) from exception
    if not isinstance(parsed, dict):
        _raise(
            "soaibench_publication_invalid_response",
            "SoAIBench publication response is invalid.",
            502,
        )
    return validate_publication_receipt(parsed, expected_score)


def _validate_success_matrix(status_code: int, receipt: JSONDict) -> None:
    duplicate = receipt.get("duplicate") is True
    if status_code == 201 and duplicate:
        _raise(
            "soaibench_publication_invalid_response",
            "SoAIBench publication response status is inconsistent.",
            502,
        )


def _is_json_content_type(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    media_type = value.split(";", 1)[0].strip().lower()
    return media_type == "application/json"


def _raise_upstream(
    response: httpx2.Response,
    raw: bytes,
    details: JSONDict | None,
) -> Never:
    retry_after = min(3600, parse_retry_after_seconds(response.headers.get("retry-after")))
    headers = {"Retry-After": str(retry_after)} if retry_after > 0 else None
    code = ""
    try:
        payload = parse_json_dict(raw, field="SoAIBench error response", reject_duplicate_keys=True)
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("code"), str):
            code = error["code"]
    except SoAIError:
        code = ""
    if response.status_code == 429:
        raise ApiError(
            "SoAIBench publication is rate limited.",
            code="soaibench_publication_rate_limited",
            http_status=429,
            details=details,
            headers=headers,
        )
    if response.status_code == 503 and code == "capacity_unavailable":
        raise ApiError(
            "SoAIBench publication capacity is unavailable.",
            code="soaibench_publication_capacity",
            http_status=503,
            details=details,
            headers=headers,
        )
    if response.status_code == 503:
        raise ApiError(
            "SoAIBench publication service is unavailable.",
            code="soaibench_publication_unavailable",
            http_status=503,
            details=details,
            headers=headers,
        )
    if 500 <= response.status_code < 600:
        raise ApiError(
            "SoAIBench publication service is unavailable.",
            code="soaibench_publication_unavailable",
            http_status=503,
            details=details,
            headers=headers,
        )
    if response.status_code == 409:
        _raise(
            "soaibench_publication_conflict",
            "SoAIBench publication conflicts with existing state.",
            409,
            details=details,
        )
    if response.status_code in {400, 413, 415, 422}:
        _raise(
            "soaibench_publication_rejected",
            "SoAIBench publication was rejected.",
            422,
            details=details,
        )
    _raise(
        "soaibench_publication_invalid_response",
        "SoAIBench publication service returned an invalid response.",
        502,
        details=details,
    )


def _upstream_details(response: httpx2.Response) -> JSONDict | None:
    request_id = response.headers.get("x-request-id")
    if isinstance(request_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", request_id):
        return {"upstream_trace_id": request_id}
    return None


def _raise(
    code: str,
    message: str,
    status: int,
    *,
    details: JSONDict | None = None,
) -> Never:
    raise ApiError(message, code=code, http_status=status, details=details)
