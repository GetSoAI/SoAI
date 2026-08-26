"""SoAI - Pure licensing V1 status resolution [backend/core/licensing/status_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.licensing.constants import CLOCK_ROLLBACK_TOLERANCE_MS, EXPIRING_WINDOW_MS
from core.licensing.types import LicensingState, LicensingStatus, LicensingStatusFacts

__all__ = (
    "licensing_state_requires_repair_plane",
    "resolve_effective_licensing_status",
    "resolve_licensing_status",
)

_RESTRICTED_STATES: frozenset[LicensingState] = frozenset(
    {
        "evaluation_pending",
        "evaluation_expired",
        "commercial_expired",
        "suspended",
        "terminated",
        "invalid_signature",
        "invalid_binding",
        "invalid_contract",
        "clock_invalid",
    }
)


def resolve_licensing_status(facts: LicensingStatusFacts) -> LicensingStatus:
    _validate_facts(facts)
    state = _resolve_state(facts)
    return LicensingStatus(
        state=state,
        requires_repair_plane=licensing_state_requires_repair_plane(state),
    )


def licensing_state_requires_repair_plane(state: LicensingState) -> bool:
    return state in _RESTRICTED_STATES


def resolve_effective_licensing_status(
    status: LicensingStatus,
    *,
    startup_repair_plane: bool,
) -> LicensingStatus:
    if status.requires_repair_plane or not startup_repair_plane:
        return status
    return LicensingStatus(state=status.state, requires_repair_plane=True)


def _validate_facts(facts: LicensingStatusFacts) -> None:
    if facts.edition not in {"soai-core", "soai-os"}:
        raise ValidationError("Licensing edition is invalid.")
    if not isinstance(facts.license_accepted, bool):
        raise ValidationError("Licensing acceptance state is invalid.")
    if facts.declaration not in {None, "personal", "organization_commercial"}:
        raise ValidationError("Licensing declaration is invalid.")
    if facts.integrity_failure not in {
        None,
        "invalid_signature",
        "invalid_binding",
        "invalid_contract",
    }:
        raise ValidationError("Licensing integrity state is invalid.")
    if facts.signed_status not in {None, "suspended", "terminated"}:
        raise ValidationError("Signed licensing status is invalid.")
    if not isinstance(facts.declaration_eligible, bool):
        raise ValidationError("Licensing declaration eligibility is invalid.")
    if facts.entitlement_type is None:
        if facts.validation_mode is not None or _has_any_boundary(facts):
            raise ValidationError("Unentitled licensing facts have entitlement boundaries.")
        return
    if facts.effective_at_ms is None or facts.validation_mode is None:
        raise ValidationError("Entitled licensing facts require effective time and mode.")
    if facts.entitlement_type in {"organization_evaluation", "commercial_term"}:
        if (
            facts.term_starts_at_ms is None
            or facts.term_ends_at_ms is None
            or facts.term_starts_at_ms >= facts.term_ends_at_ms
        ):
            raise ValidationError("Fixed-term licensing boundaries are invalid.")
        expected_mode = (
            "local_only" if facts.entitlement_type == "organization_evaluation" else "term_fixed"
        )
        if facts.validation_mode != expected_mode or _has_continuity_boundary(facts):
            raise ValidationError("Fixed-term licensing facts are contradictory.")
        return
    if facts.entitlement_type == "commercial_continuity":
        if facts.validation_mode != "term_fixed":
            raise ValidationError("Commercial continuity facts are contradictory.")
        continuity_start = facts.continuity_starts_at_ms
        continuity_end = facts.continuity_ends_at_ms
        if continuity_start is None or continuity_end is None:
            raise ValidationError("Commercial continuity facts are contradictory.")
        if (
            continuity_start >= continuity_end
            or facts.term_starts_at_ms is not None
            or facts.term_ends_at_ms is not None
        ):
            raise ValidationError("Commercial continuity facts are contradictory.")
        return
    if facts.validation_mode != "local_only" or _has_any_boundary(facts):
        raise ValidationError("Perpetual licensing facts are contradictory.")


def _has_any_boundary(facts: LicensingStatusFacts) -> bool:
    return any(
        boundary is not None
        for boundary in (
            facts.term_starts_at_ms,
            facts.term_ends_at_ms,
            facts.continuity_starts_at_ms,
            facts.continuity_ends_at_ms,
        )
    )


def _has_continuity_boundary(facts: LicensingStatusFacts) -> bool:
    return facts.continuity_starts_at_ms is not None or facts.continuity_ends_at_ms is not None


def _resolve_state(facts: LicensingStatusFacts) -> LicensingState:
    if facts.integrity_failure is not None:
        return facts.integrity_failure
    if facts.signed_status is not None:
        return facts.signed_status
    if not facts.license_accepted or not facts.declaration_eligible:
        return "evaluation_pending"
    if facts.entitlement_type is None:
        if facts.edition == "soai-core" and facts.declaration == "personal":
            return "personal_declared"
        return "evaluation_pending"
    if facts.entitlement_type == "personal_os_perpetual":
        return "personal_os_perpetual_active"
    if facts.entitlement_type == "commercial_full_perpetual":
        return "commercial_perpetual_active"
    if facts.now_ms + CLOCK_ROLLBACK_TOLERANCE_MS < facts.verified_time_high_water_ms:
        return "clock_invalid"
    if facts.entitlement_type == "organization_evaluation":
        return _resolve_evaluation(facts)
    if facts.entitlement_type == "commercial_continuity":
        return _resolve_continuity(facts)
    return _resolve_commercial_term(facts)


def _resolve_evaluation(facts: LicensingStatusFacts) -> LicensingState:
    term_end = facts.term_ends_at_ms
    if term_end is None or facts.now_ms >= term_end:
        return "evaluation_expired"
    if term_end - facts.now_ms <= EXPIRING_WINDOW_MS:
        return "evaluation_expiring"
    return "evaluation_active"


def _resolve_commercial_term(facts: LicensingStatusFacts) -> LicensingState:
    term_end = facts.term_ends_at_ms
    if term_end is None or facts.now_ms >= term_end:
        return "commercial_expired"
    if term_end - facts.now_ms <= EXPIRING_WINDOW_MS:
        return "commercial_expiring"
    return "commercial_active"


def _resolve_continuity(facts: LicensingStatusFacts) -> LicensingState:
    continuity_end = facts.continuity_ends_at_ms
    if continuity_end is None or facts.now_ms >= continuity_end:
        return "commercial_expired"
    return "commercial_continuity"
