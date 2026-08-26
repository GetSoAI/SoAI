"""SoAI - API request payload readers [backend/features/api/runtime/request_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.serialization.json import normalize_for_json, normalize_to_json_dict
from core.serialization.json_parsing import MAX_JSON_NESTING_DEPTH, parse_json_value
from core.types.json import is_json_value
from features.api.runtime.errors import (
    raise_invalid_request,
    raise_payload_too_large,
    raise_server_error,
)
from features.api.runtime.request_media_types import require_non_multipart_media_type

if TYPE_CHECKING:
    from fastapi import Request

    from core.types.json import JSONDict, JSONValue

__all__ = (
    "read_bounded_json_body_or_raise",
    "read_bounded_json_dict_payload_or_raise",
    "read_bounded_body_bytes_or_raise",
    "read_json_body",
    "read_json_dict_payload",
    "read_json_object_payload_or_raise",
    "read_json_object_with_required_field_or_raise",
    "read_optional_json_dict_payload",
    "read_optional_json_dict_payload_or_raise",
    "read_required_json_dict_payload",
    "read_required_json_dict_payload_or_raise",
)

REQUEST_BODY_CHUNK_LIMIT = 65_536
BOUNDED_BODY_READ_TIMEOUT_SECONDS = 5.0


async def read_json_body(
    request: Request,
    *,
    invalid_json_message: str,
) -> JSONValue:
    require_non_multipart_media_type(request)
    try:
        payload = normalize_for_json(await request.json())
    except ValueError as exception:
        raise ValidationError(invalid_json_message) from exception
    if is_json_value(payload):
        return payload
    raise ValidationError(invalid_json_message)


def _resolve_content_length(request: Request) -> int | None:
    raw_content_length = str(request.headers.get("content-length", "")).strip()
    if not raw_content_length:
        return None
    try:
        content_length = int(raw_content_length)
    except ValueError as exception:
        raise ValidationError("Content-Length header is invalid.") from exception
    if content_length < 0:
        raise ValidationError("Content-Length header is invalid.")
    return content_length


async def _read_bounded_body_bytes(request: Request, *, max_body_bytes: int) -> bytes:
    require_non_multipart_media_type(request)
    if max_body_bytes <= 0:
        raise StateError("Maximum request body size is invalid.")
    content_length = _resolve_content_length(request)
    if content_length is not None and content_length > max_body_bytes:
        raise ValueError("Request body is too large.")
    chunks: list[bytes] = []
    total_size = 0
    async with asyncio.timeout(BOUNDED_BODY_READ_TIMEOUT_SECONDS):
        async for chunk in request.stream():
            chunk_size = len(chunk)
            if chunk_size > REQUEST_BODY_CHUNK_LIMIT and chunk_size > max_body_bytes:
                raise ValueError("Request body is too large.")
            total_size += chunk_size
            if total_size > max_body_bytes:
                raise ValueError("Request body is too large.")
            chunks.append(chunk)
    return b"".join(chunks)


async def read_bounded_body_bytes_or_raise(
    request: Request,
    *,
    max_body_bytes: int,
    invalid_body_message: str,
    payload_too_large_message: str,
) -> bytes:
    try:
        return await _read_bounded_body_bytes(request, max_body_bytes=max_body_bytes)
    except ValueError:
        raise_payload_too_large(request, payload_too_large_message)
    except TimeoutError:
        raise_invalid_request(request, invalid_body_message)


async def read_bounded_json_body_or_raise(
    request: Request,
    *,
    max_body_bytes: int,
    invalid_json_message: str,
    payload_too_large_message: str,
    strict_utf8: bool = False,
    reject_duplicate_keys: bool = False,
) -> JSONValue:
    try:
        raw_body = await read_bounded_body_bytes_or_raise(
            request,
            max_body_bytes=max_body_bytes,
            invalid_body_message=invalid_json_message,
            payload_too_large_message=payload_too_large_message,
        )
        payload = parse_json_value(
            raw_body,
            field="request body",
            max_depth=MAX_JSON_NESTING_DEPTH,
            strict_utf8=strict_utf8,
            reject_duplicate_keys=reject_duplicate_keys,
        )
    except ValidationError:
        raise_invalid_request(request, invalid_json_message)
    if is_json_value(payload):
        return payload
    raise_invalid_request(request, invalid_json_message)


async def read_bounded_json_dict_payload_or_raise(
    request: Request,
    *,
    max_body_bytes: int,
    invalid_json_message: str,
    invalid_object_message: str,
    payload_too_large_message: str,
    normalization_error_message: str,
    strict_utf8: bool = False,
    reject_duplicate_keys: bool = False,
) -> JSONDict:
    raw_payload = await read_bounded_json_body_or_raise(
        request,
        max_body_bytes=max_body_bytes,
        invalid_json_message=invalid_json_message,
        payload_too_large_message=payload_too_large_message,
        strict_utf8=strict_utf8,
        reject_duplicate_keys=reject_duplicate_keys,
    )
    if not isinstance(raw_payload, dict):
        raise_invalid_request(request, invalid_object_message)
    try:
        return normalize_to_json_dict(raw_payload, message=normalization_error_message)
    except (StateError, ValidationError):
        raise_server_error(request, normalization_error_message)


async def read_json_dict_payload(
    request: Request,
    *,
    invalid_json_message: str,
    invalid_object_message: str,
    normalization_error_message: str,
) -> JSONDict:
    raw_payload = await read_json_body(request, invalid_json_message=invalid_json_message)
    if not isinstance(raw_payload, dict):
        raise ValidationError(invalid_object_message)
    try:
        return normalize_to_json_dict(raw_payload, message=normalization_error_message)
    except (StateError, ValidationError) as exception:
        raise StateError(normalization_error_message) from exception


async def read_optional_json_dict_payload(
    request: Request,
    *,
    invalid_message: str,
    server_error_message: str,
) -> JSONDict:
    require_non_multipart_media_type(request)
    raw_body = await request.body()
    if not raw_body.strip():
        return {}
    return await read_json_dict_payload(
        request,
        invalid_json_message=invalid_message,
        invalid_object_message=invalid_message,
        normalization_error_message=server_error_message,
    )


async def read_required_json_dict_payload(
    request: Request,
    *,
    invalid_message: str,
    server_error_message: str,
) -> JSONDict:
    payload = await read_optional_json_dict_payload(
        request,
        invalid_message=invalid_message,
        server_error_message=server_error_message,
    )
    if not payload:
        raise ValidationError(invalid_message)
    return payload


async def read_json_object_payload_or_raise(
    request: Request,
    *,
    invalid_json_message: str,
    invalid_object_message: str,
) -> JSONDict:
    try:
        return await read_json_dict_payload(
            request,
            invalid_json_message=invalid_json_message,
            invalid_object_message=invalid_object_message,
            normalization_error_message=invalid_object_message,
        )
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    except StateError:
        raise_server_error(request, invalid_object_message)


async def read_json_object_with_required_field_or_raise(
    request: Request,
    *,
    required_field: str,
    invalid_json_message: str,
    invalid_object_message: str,
    missing_field_message: str,
) -> JSONDict:
    payload = await read_json_object_payload_or_raise(
        request,
        invalid_json_message=invalid_json_message,
        invalid_object_message=invalid_object_message,
    )
    if required_field not in payload:
        raise_invalid_request(request, missing_field_message)
    return payload


async def read_optional_json_dict_payload_or_raise(
    request: Request,
    *,
    invalid_message: str,
    server_error_message: str,
) -> JSONDict:
    try:
        return await read_optional_json_dict_payload(
            request,
            invalid_message=invalid_message,
            server_error_message=server_error_message,
        )
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    except StateError as exception:
        raise_server_error(request, str(exception))


async def read_required_json_dict_payload_or_raise(
    request: Request,
    *,
    invalid_message: str,
    server_error_message: str,
) -> JSONDict:
    try:
        return await read_required_json_dict_payload(
            request,
            invalid_message=invalid_message,
            server_error_message=server_error_message,
        )
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    except StateError as exception:
        raise_server_error(request, str(exception))
