"""SoAI - HTTP idempotency identity extraction [backend/features/api/runtime/idempotency.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from starlette.requests import Request

from core.errors.exceptions import ValidationError
from core.mutations.identifiers import require_mutation_request_id

__all__ = ("require_idempotency_key",)


def require_idempotency_key(request: Request) -> str:
    value = request.headers.get("Idempotency-Key")
    if value is None:
        raise ValidationError("Idempotency-Key header is required.")
    return require_mutation_request_id(value)
