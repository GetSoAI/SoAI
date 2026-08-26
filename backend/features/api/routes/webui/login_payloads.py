"""SoAI - WebUI login payload parsing [backend/features/api/routes/webui/login_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request
from pydantic import ValidationError

from core.config.clamped_numeric import read_config_int_min_clamped
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_invalid_request
from features.api.runtime.request_payloads import (
    read_bounded_json_dict_payload_or_raise,
)
from features.api.schemas.users import LoginPayload

__all__ = ("read_login_payload_or_raise",)

DEFAULT_LOGIN_MAX_BODY_BYTES = 8192


async def read_login_payload_or_raise(request: Request, api_context: ApiContext) -> LoginPayload:
    content_type = request.headers.get("content-type", "")
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise_invalid_request(request, "Invalid login payload.")
    max_body_bytes = read_config_int_min_clamped(
        api_context.dependencies.config,
        "SERVER.WEBUI.LOGIN_SECURITY.MAX_BODY_BYTES",
        DEFAULT_LOGIN_MAX_BODY_BYTES,
        minimum=512,
    )
    payload = await read_bounded_json_dict_payload_or_raise(
        request,
        max_body_bytes=max_body_bytes,
        invalid_json_message="Invalid login payload.",
        invalid_object_message="Invalid login payload.",
        payload_too_large_message="Login payload is too large.",
        normalization_error_message="Failed to normalize login payload.",
    )
    try:
        return LoginPayload.model_validate(payload)
    except ValidationError:
        raise_invalid_request(request, "Invalid login payload.")
