"""SoAI - Root-signed full-perpetual grant validation [backend/core/licensing/grant_certificate.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from core.errors.exceptions import ValidationError
from core.licensing.canonicalization import canonicalize_licensing_json
from core.licensing.capabilities import (
    require_commercial_licensing_capabilities,
    require_licensing_capabilities,
)
from core.licensing.encoding import decode_licensing_base64url
from core.licensing.entitlement_payloads import ParsedEntitlementPayload
from core.licensing.errors import LicensingIntegrityError
from core.licensing.timestamps import parse_licensing_timestamp
from core.licensing.trust import IssuerAuthorizationCatalog, issuer_key_identity
from core.types.json import JSONDict, JSONValue
from core.validation.object_fields import require_exact_json_fields
from core.validation.record_fields import require_json_object

_ENVELOPE_FIELDS = frozenset(
    ("schema_version", "payload", "root_key_id", "signature_domain", "signature")
)
_PAYLOAD_FIELDS = frozenset(
    (
        "schema_version",
        "document_type",
        "request_id",
        "license_id",
        "customer_id",
        "licensed_product_scope",
        "agreement_reference",
        "effective_at",
        "licensed_capabilities",
        "allowed_production_deployments",
        "allowed_non_production_deployments",
    )
)


def validate_full_perpetual_grant_certificate(
    certificate_value: JSONValue,
    trust_catalog: IssuerAuthorizationCatalog,
    entitlement: ParsedEntitlementPayload,
) -> None:
    certificate = require_json_object(
        certificate_value,
        label="Full perpetual grant certificate",
        build_error=ValidationError,
        invalid_message="Full perpetual grant certificate must be an object.",
    )
    require_exact_json_fields(
        certificate,
        allowed_fields=_ENVELOPE_FIELDS,
        label="Full perpetual grant certificate",
    )
    if (
        certificate.get("schema_version") != 1
        or certificate.get("signature_domain") != "soai-full-perpetual-grant-v1"
    ):
        raise ValidationError("Full perpetual grant certificate contract is invalid.")
    payload = require_json_object(
        certificate.get("payload"),
        label="Full perpetual grant payload",
        build_error=ValidationError,
        invalid_message="Full perpetual grant payload must be an object.",
    )
    require_exact_json_fields(
        payload,
        allowed_fields=_PAYLOAD_FIELDS,
        label="Full perpetual grant",
    )
    _validate_payload(payload)
    root_public_key = trust_catalog.root_public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    if certificate.get("root_key_id") != issuer_key_identity(root_public_key):
        raise LicensingIntegrityError.for_failure(
            "invalid_signature",
            "Full perpetual grant root identity is invalid.",
        )
    signature_text = certificate.get("signature")
    if not isinstance(signature_text, str):
        raise ValidationError("Full perpetual grant signature is invalid.")
    try:
        trust_catalog.root_public_key.verify(
            decode_licensing_base64url(signature_text, expected_bytes=64),
            b"".join((b"soai-full-perpetual-grant-v1\0", canonicalize_licensing_json(payload))),
        )
    except InvalidSignature as exception:
        raise LicensingIntegrityError.for_failure(
            "invalid_signature",
            "Full perpetual grant signature is invalid.",
        ) from exception
    _require_entitlement_match(payload, entitlement)


def _validate_payload(payload: JSONDict) -> None:
    if (
        payload.get("schema_version") != 1
        or payload.get("document_type") != "commercial_full_perpetual_grant"
    ):
        raise ValidationError("Full perpetual grant payload contract is invalid.")
    request_id = payload.get("request_id")
    license_id = payload.get("license_id")
    agreement_reference = payload.get("agreement_reference")
    customer_id = payload.get("customer_id")
    if (
        not isinstance(request_id, str)
        or re.fullmatch(r"gpr_[A-Za-z0-9_-]{22}", request_id) is None
    ):
        raise ValidationError("Full perpetual grant request identity is invalid.")
    if (
        not isinstance(license_id, str)
        or re.fullmatch(r"lic_[A-Za-z0-9_-]{22}", license_id) is None
    ):
        raise ValidationError("Full perpetual grant license identity is invalid.")
    if (
        not isinstance(agreement_reference, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", agreement_reference) is None
    ):
        raise ValidationError("Full perpetual grant agreement reference is invalid.")
    if (
        not isinstance(customer_id, str)
        or re.fullmatch(r"cus_[A-Za-z0-9_-]{22}", customer_id) is None
    ):
        raise ValidationError("Full perpetual grant customer identity is invalid.")
    if payload.get("licensed_product_scope") not in {
        "soai_core",
        "soai_os",
        "soai_core_and_os",
    }:
        raise ValidationError("Full perpetual grant product scope is invalid.")
    parse_licensing_timestamp(payload.get("effective_at"), field="grant effective_at")
    capabilities = require_licensing_capabilities(payload.get("licensed_capabilities"))
    require_commercial_licensing_capabilities(capabilities)
    _validate_deployment_allowances(payload)


def _validate_deployment_allowances(payload: JSONDict) -> None:
    for field in (
        "allowed_production_deployments",
        "allowed_non_production_deployments",
    ):
        allowance = payload.get(field)
        if (
            isinstance(allowance, bool)
            or not isinstance(allowance, int)
            or not 1 <= allowance <= 1_000_000
        ):
            raise ValidationError("Full perpetual grant deployment allowance is invalid.")


def _require_entitlement_match(payload: JSONDict, entitlement: ParsedEntitlementPayload) -> None:
    values = entitlement.values
    compared_fields = (
        "license_id",
        "licensed_product_scope",
        "effective_at",
        "licensed_capabilities",
        "allowed_production_deployments",
        "allowed_non_production_deployments",
    )
    if any(payload.get(field) != values.get(field) for field in compared_fields):
        raise LicensingIntegrityError.for_failure(
            "invalid_contract",
            "Full perpetual grant certificate does not match the entitlement.",
        )


__all__ = ("validate_full_perpetual_grant_certificate",)
