"""SoAI - Strict chat preset HTTP input validation [backend/features/api/routes/webui/chat_preset_request_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import pydantic

from core.chat_presets.identity import require_chat_preset_id
from core.errors.exceptions import PayloadTooLargeError, ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.types.json import JSONDict
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from features.api.runtime.errors import raise_invalid_request, raise_payload_too_large
from features.api.runtime.request_payloads import read_bounded_json_dict_payload_or_raise

if TYPE_CHECKING:
    from fastapi import Request

__all__ = (
    "map_chat_preset_validation_error",
    "read_chat_preset_payload",
    "require_addressed_delete_query",
    "require_chat_preset_path_id",
    "require_reset_query",
)

CHAT_PRESET_MAX_BODY_BYTES = 128 * 1024


async def read_chat_preset_payload[ModelType: SoAIV1StrictModel](
    request: Request,
    model_type: type[ModelType],
) -> tuple[ModelType, JSONDict]:
    payload = await read_bounded_json_dict_payload_or_raise(
        request,
        max_body_bytes=CHAT_PRESET_MAX_BODY_BYTES,
        invalid_json_message="Invalid chat preset JSON payload.",
        invalid_object_message="Chat preset payload must be an object.",
        payload_too_large_message="Chat preset payload exceeds the 128 KiB limit.",
        normalization_error_message="Invalid chat preset payload.",
        strict_utf8=True,
        reject_duplicate_keys=True,
    )
    try:
        return model_type.model_validate(payload), payload
    except pydantic.ValidationError:
        raise_invalid_request(request, "Invalid chat preset payload.")


def require_chat_preset_path_id(request: Request, preset_id: str) -> str:
    try:
        return require_chat_preset_id(preset_id)
    except ValidationError:
        raise_invalid_request(request, "Invalid chat preset identifier.")


def _require_exact_query(
    request: Request,
    *,
    expected_name: str,
) -> str:
    query_items = list(request.query_params.multi_items())
    if len(query_items) != 1 or query_items[0][0] != expected_name:
        raise_invalid_request(request, "Invalid chat preset query parameters.")
    return query_items[0][1]


def require_addressed_delete_query(request: Request) -> int:
    raw_revision = _require_exact_query(request, expected_name="expected_revision")
    if not raw_revision or raw_revision[0] == "0" or not raw_revision.isascii():
        raise_invalid_request(request, "Invalid expected_revision query value.")
    if not all("0" <= character <= "9" for character in raw_revision):
        raise_invalid_request(request, "Invalid expected_revision query value.")
    maximum_revision = str(JAVASCRIPT_SAFE_INTEGER_MAX)
    if len(raw_revision) > len(maximum_revision) or (
        len(raw_revision) == len(maximum_revision) and raw_revision > maximum_revision
    ):
        raise_invalid_request(request, "Invalid expected_revision query value.")
    revision = int(raw_revision)
    return revision


def require_reset_query(request: Request) -> None:
    if _require_exact_query(request, expected_name="confirm") != "true":
        raise_invalid_request(request, "Reset confirmation must be exactly true.")


def map_chat_preset_validation_error(request: Request, exception: Exception) -> None:
    if isinstance(exception, PayloadTooLargeError):
        raise_payload_too_large(request, "Chat preset sections exceed the 64 KiB limit.")
    if isinstance(exception, ValidationError):
        raise_invalid_request(request, "Invalid chat preset settings.")
    raise exception
