"""SoAI - Initial and reconciliation machine requests [backend/core/licensing/machine_protocol.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.errors.exceptions import ValidationError
from core.licensing.identifiers import require_licensing_identifier
from core.licensing.machine_request_signing import (
    MAX_MACHINE_REQUEST_BYTES,
    PreparedLicensingRequest,
    prepare_signed_machine_request,
)
from core.types.json import JSONDict, JSONValue


def prepare_evaluation_request(
    private_key: Ed25519PrivateKey,
    *,
    idempotency_key: str,
    instance_id: str,
    soai_version: str,
    organization: JSONDict,
    legal_acceptances: list[JSONValue],
    request_nonce: bytes | None = None,
) -> PreparedLicensingRequest:
    return prepare_signed_machine_request(
        private_key,
        "evaluation",
        idempotency_key,
        instance_id,
        soai_version,
        request_nonce,
        {
            "deployment_product": "soai_core",
            "organization": organization,
            "legal_acceptances": legal_acceptances,
        },
    )


def prepare_activation_request(
    private_key: Ed25519PrivateKey,
    *,
    idempotency_key: str,
    instance_id: str,
    soai_version: str,
    deployment_product: str,
    activation_source: str,
    pending_evaluation_id: str | None,
    activation_credential: str | None,
    deployment_environment: str | None,
    legal_acceptances: list[JSONValue],
    request_nonce: bytes | None = None,
) -> PreparedLicensingRequest:
    if deployment_product not in {"soai_core", "soai_os"}:
        raise ValidationError("Licensing deployment product is invalid.")
    if activation_source not in {"evaluation", "credential"}:
        raise ValidationError("Licensing activation source is invalid.")
    if activation_source == "evaluation":
        if (
            pending_evaluation_id is None
            or activation_credential is not None
            or deployment_product != "soai_core"
            or deployment_environment is not None
        ):
            raise ValidationError("Licensing evaluation activation input is contradictory.")
        require_licensing_identifier(
            pending_evaluation_id, label="Licensing pending evaluation identity"
        )
    elif (
        activation_credential is None
        or not 1 <= len(activation_credential) <= 192
        or pending_evaluation_id is not None
        or (
            deployment_environment is not None
            and deployment_environment not in {"production", "non_production"}
        )
    ):
        raise ValidationError("Licensing credential activation input is contradictory.")
    return prepare_signed_machine_request(
        private_key,
        "activation",
        idempotency_key,
        instance_id,
        soai_version,
        request_nonce,
        {
            "deployment_product": deployment_product,
            "activation_source": activation_source,
            "pending_evaluation_id": pending_evaluation_id,
            "activation_credential": activation_credential,
            "deployment_environment": deployment_environment,
            "legal_acceptances": legal_acceptances,
        },
    )


def prepare_operation_reconciliation_request(
    private_key: Ed25519PrivateKey,
    *,
    idempotency_key: str,
    instance_id: str,
    soai_version: str,
    operation_idempotency_key: str,
    request_digest: str,
    request_nonce: bytes | None = None,
) -> PreparedLicensingRequest:
    require_licensing_identifier(operation_idempotency_key, label="Licensing operation identity")
    if re.fullmatch(r"sha256:[a-f0-9]{64}", request_digest) is None:
        raise ValidationError("Licensing operation request digest is invalid.")
    return prepare_signed_machine_request(
        private_key,
        "operation-reconciliation",
        idempotency_key,
        instance_id,
        soai_version,
        request_nonce,
        {
            "operation_idempotency_key": operation_idempotency_key,
            "request_digest": request_digest,
        },
    )


def prepare_offline_activation_request(
    private_key: Ed25519PrivateKey,
    *,
    idempotency_key: str,
    instance_id: str,
    soai_version: str,
    licensed_product_scope: str,
    deployment_product: str,
    deployment_environment: str | None,
    license_reference: str | None,
    request_nonce: bytes | None = None,
) -> PreparedLicensingRequest:
    return prepare_signed_machine_request(
        private_key,
        "offline-activation",
        idempotency_key,
        instance_id,
        soai_version,
        request_nonce,
        {
            "licensed_product_scope": licensed_product_scope,
            "deployment_product": deployment_product,
            "deployment_environment": deployment_environment,
            "license_reference": license_reference,
        },
    )


__all__ = (
    "MAX_MACHINE_REQUEST_BYTES",
    "PreparedLicensingRequest",
    "prepare_activation_request",
    "prepare_evaluation_request",
    "prepare_offline_activation_request",
    "prepare_operation_reconciliation_request",
)
