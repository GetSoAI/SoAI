"""SoAI - Provider mutation HTTP preconditions [backend/features/api/routes/plugins/provider_mutation_headers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from starlette.requests import Request

from core.errors.exceptions import ValidationError

__all__ = ("require_provider_revision",)

_REVISION_ETAG_PATTERN = r'"(0|[1-9][0-9]*)"\Z'


def require_provider_revision(request: Request) -> int:
    value = request.headers.get("If-Match")
    if value is None:
        raise ValidationError("If-Match header is required.")
    match = re.fullmatch(_REVISION_ETAG_PATTERN, value)
    if match is None:
        raise ValidationError("If-Match must contain one quoted non-negative integer revision.")
    revision = int(match.group(1))
    if revision > 9_007_199_254_740_991:
        raise ValidationError("If-Match revision exceeds the supported range.")
    return revision
