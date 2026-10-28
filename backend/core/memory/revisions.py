"""SoAI - Canonical memory snapshot revisions [backend/core/memory/revisions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from hashlib import sha256

from core.errors.exceptions import ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.sha256_hexdigest import is_canonical_sha256_hexdigest
from core.types.json import JSONDict

__all__ = (
    "calculate_memory_revision",
    "memory_management_error",
    "require_memory_revision",
)


def calculate_memory_revision(snapshot: JSONDict) -> str:
    return sha256(serialize_json_compact_stable_strict(snapshot).encode("utf-8")).hexdigest()


def memory_management_error(code: str, message: str, status: int = 409) -> ValidationError:
    error = ValidationError(message)
    apply_public_error_payload(
        error, ErrorPublicPayload(code=code, message=message, http_status=status)
    )
    return error


def require_memory_revision(expected: str, actual: str) -> None:
    if not is_canonical_sha256_hexdigest(expected):
        raise memory_management_error(
            "memory_invalid_revision",
            "Refresh the memory library and review the current entry.",
            422,
        )
    if expected != actual:
        raise memory_management_error(
            "memory_revision_changed",
            "This memory changed. Review its current contents before saving.",
        )
