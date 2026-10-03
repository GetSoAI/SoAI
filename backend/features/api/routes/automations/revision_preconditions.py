"""SoAI - Automation definition revision HTTP preconditions [backend/features/api/routes/automations/revision_preconditions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from features.api.runtime.errors import raise_invalid_request

if TYPE_CHECKING:
    from starlette.requests import Request

    from core.types.json import JSONDict

__all__ = (
    "build_automation_etag_headers",
    "read_automation_expected_revision",
)

_REVISION_ETAG_PATTERN = r'"([0-9a-f]{64})"'


def read_automation_expected_revision(request: Request) -> str | None:
    value = request.headers.get("If-Match")
    if value is None:
        return None
    match = re.fullmatch(_REVISION_ETAG_PATTERN, value.strip())
    if match is None:
        raise_invalid_request(
            request,
            "If-Match must contain one quoted automation revision.",
            error_type="invalid_automation_revision",
        )
    return match.group(1)


def build_automation_etag_headers(record: JSONDict) -> dict[str, str]:
    revision = record.get("revision")
    if not isinstance(revision, str) or not revision:
        raise StateError("Automation record is missing its revision.")
    return {"ETag": f'"{revision}"'}
