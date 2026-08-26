"""SoAI - Licensing operation outcome taxonomy [backend/core/licensing/operation_outcomes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "ACTIONABLE_AUTHORITY_FAILURE_CODES",
    "licensing_operation_terminal_codes",
)

ACTIONABLE_AUTHORITY_FAILURE_CODES = (
    "invalid_credential",
    "personal_capacity_reached",
    "production_capacity_reached",
    "non_production_capacity_reached",
    "licensed_product_scope_mismatch",
    "license_not_effective",
    "license_expired",
    "license_suspended",
    "license_terminated",
    "evaluation_ineligible",
    "provider_outcome_unknown",
    "renewal_not_reconciled",
)


def licensing_operation_terminal_codes() -> frozenset[str]:
    return frozenset(
        (
            *ACTIONABLE_AUTHORITY_FAILURE_CODES,
            "activation_not_found",
            "operation_not_found",
            "idempotency_conflict",
            "invalid_input",
            "authority_rejected",
            "invalid_signature",
            "invalid_binding",
            "invalid_contract",
        )
    )
