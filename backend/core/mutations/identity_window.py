"""SoAI - Mutation identity admission window [backend/core/mutations/identity_window.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ApiError, ValidationError
from core.mutations.identifiers import extract_mutation_request_timestamp_ms

IDENTITY_MAX_SKEW_MS = 600_000
IDENTITY_RETENTION_MS = 2_592_000_000


class MutationIdentityTimeSkewError(ApiError):
    def __init__(self, server_time_ms: int) -> None:
        super().__init__(
            "Mutation request identity is outside the server-time admission window.",
            code="identity_time_skew",
            http_status=422,
            details={"server_time_ms": server_time_ms},
        )


class MutationIdentityExpiredError(ValidationError):
    code: str | int = "mutation_identity_expired"


def validate_mutation_identity_window(request_id: str, server_time_ms: int) -> None:
    identity_timestamp_ms = extract_mutation_request_timestamp_ms(request_id)
    if identity_timestamp_ms < server_time_ms - IDENTITY_RETENTION_MS:
        raise MutationIdentityExpiredError("Mutation request identity has expired.")
    if abs(identity_timestamp_ms - server_time_ms) > IDENTITY_MAX_SKEW_MS:
        raise MutationIdentityTimeSkewError(server_time_ms)


__all__ = (
    "IDENTITY_RETENTION_MS",
    "MutationIdentityExpiredError",
    "MutationIdentityTimeSkewError",
    "validate_mutation_identity_window",
)
