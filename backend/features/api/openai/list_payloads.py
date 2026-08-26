"""SoAI - OpenAI list response payload helpers [backend/features/api/openai/list_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from core.openai.list_payloads import build_openai_list_payload
from core.types.json_value import filter_json_mapping_strict
from features.api.runtime.response_body import create_json_body_response

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_openai_list_response",
    "parse_metadata_filters",
)


def parse_metadata_filters(request: Request) -> dict[str, str]:
    filters: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        if not key.startswith("metadata[") or not key.endswith("]"):
            continue
        inner = key[len("metadata[") : -1].strip()
        if not inner:
            continue
        filters[inner] = value
    return filters


def build_openai_list_response(*, data: list[JSONDict], has_more: bool) -> JSONResponse:
    return create_json_body_response(
        content=filter_json_mapping_strict(
            build_openai_list_payload(data=data, has_more=has_more),
            error_message="OpenAI list payload must be JSON-compatible.",
        ),
    )
