"""SoAI - Bound deployment machine requests [backend/core/licensing/deployment_request_protocol.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.errors.exceptions import ValidationError
from core.licensing.identifiers import require_licensing_identifier
from core.licensing.machine_request_signing import (
    PreparedLicensingRequest,
    prepare_signed_machine_request,
)
from core.types.json import JSONDict, JSONValue


def prepare_os_evaluation_conversion_request(
    private_key: Ed25519PrivateKey,
    *,
    idempotency_key: str,
    instance_id: str,
    soai_version: str,
    deployment_id: str,
    entitlement_generation: int,
    organization: JSONDict,
    legal_acceptances: list[JSONValue],
    request_nonce: bytes | None = None,
) -> PreparedLicensingRequest:
    return _deployment_request(
        private_key,
        "os-evaluation-conversion",
        idempotency_key,
        instance_id,
        soai_version,
        deployment_id,
        entitlement_generation,
        request_nonce,
        {
            "deployment_product": "soai_os",
            "organization": organization,
            "legal_acceptances": legal_acceptances,
        },
    )


def prepare_os_evaluation_reversion_request(
    private_key: Ed25519PrivateKey,
    *,
    idempotency_key: str,
    instance_id: str,
    soai_version: str,
    deployment_id: str,
    entitlement_generation: int,
    request_nonce: bytes | None = None,
) -> PreparedLicensingRequest:
    return _deployment_request(
        private_key,
        "os-evaluation-reversion",
        idempotency_key,
        instance_id,
        soai_version,
        deployment_id,
        entitlement_generation,
        request_nonce,
        {"company_use_ended": True, "company_data_handled": True},
    )


def prepare_commercial_conversion_request(
    private_key: Ed25519PrivateKey,
    *,
    idempotency_key: str,
    instance_id: str,
    soai_version: str,
    deployment_id: str,
    entitlement_generation: int,
    activation_credential: str,
    deployment_product: str,
    deployment_environment: str,
    legal_acceptances: list[JSONValue],
    request_nonce: bytes | None = None,
) -> PreparedLicensingRequest:
    return _deployment_request(
        private_key,
        "commercial-conversion",
        idempotency_key,
        instance_id,
        soai_version,
        deployment_id,
        entitlement_generation,
        request_nonce,
        {
            "activation_credential": activation_credential,
            "deployment_product": deployment_product,
            "deployment_environment": deployment_environment,
            "legal_acceptances": legal_acceptances,
        },
    )


def prepare_deployment_reclassification_request(
    private_key: Ed25519PrivateKey,
    *,
    idempotency_key: str,
    instance_id: str,
    soai_version: str,
    deployment_id: str,
    entitlement_generation: int,
    deployment_environment: str,
    request_nonce: bytes | None = None,
) -> PreparedLicensingRequest:
    return _deployment_request(
        private_key,
        "deployment-reclassification",
        idempotency_key,
        instance_id,
        soai_version,
        deployment_id,
        entitlement_generation,
        request_nonce,
        {"deployment_environment": deployment_environment},
    )


def prepare_term_renewal_request(
    private_key: Ed25519PrivateKey,
    *,
    idempotency_key: str,
    instance_id: str,
    soai_version: str,
    deployment_id: str,
    entitlement_generation: int,
    current_term_id: str,
    request_nonce: bytes | None = None,
) -> PreparedLicensingRequest:
    require_licensing_identifier(current_term_id, label="Licensing term identity")
    return _deployment_request(
        private_key,
        "term-renewal",
        idempotency_key,
        instance_id,
        soai_version,
        deployment_id,
        entitlement_generation,
        request_nonce,
        {"current_term_id": current_term_id},
    )


def prepare_deactivation_request(
    private_key: Ed25519PrivateKey,
    *,
    idempotency_key: str,
    instance_id: str,
    soai_version: str,
    deployment_id: str,
    entitlement_generation: int,
    reason: str,
    request_nonce: bytes | None = None,
) -> PreparedLicensingRequest:
    if reason not in {"rehost", "retired", "disaster_recovery", "other"}:
        raise ValidationError("Licensing deactivation reason is invalid.")
    return _deployment_request(
        private_key,
        "deactivation",
        idempotency_key,
        instance_id,
        soai_version,
        deployment_id,
        entitlement_generation,
        request_nonce,
        {"reason": reason},
    )


def _deployment_request(
    private_key: Ed25519PrivateKey,
    operation: str,
    idempotency_key: str,
    instance_id: str,
    soai_version: str,
    deployment_id: str,
    generation: int,
    request_nonce: bytes | None,
    specific: JSONDict,
) -> PreparedLicensingRequest:
    require_licensing_identifier(deployment_id, label="Licensing deployment identity")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise ValidationError("Licensing entitlement generation is invalid.")
    return prepare_signed_machine_request(
        private_key,
        operation,
        idempotency_key,
        instance_id,
        soai_version,
        request_nonce,
        {
            "deployment_id": deployment_id,
            "entitlement_generation": generation,
            **specific,
        },
    )


__all__ = (
    "prepare_commercial_conversion_request",
    "prepare_deactivation_request",
    "prepare_deployment_reclassification_request",
    "prepare_os_evaluation_conversion_request",
    "prepare_os_evaluation_reversion_request",
    "prepare_term_renewal_request",
)
