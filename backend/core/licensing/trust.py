"""SoAI - Root-verified licensing issuer trust [backend/core/licensing/trust.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.errors.exceptions import ValidationError
from core.licensing.canonicalization import (
    canonicalize_licensing_json,
    parse_canonical_licensing_document,
)
from core.licensing.encoding import decode_licensing_base64url
from core.licensing.timestamps import parse_licensing_timestamp
from core.types.json import JSONValue
from core.validation.object_fields import require_exact_json_fields
from core.validation.record_fields import require_json_object

__all__ = (
    "ISSUER_AUTHORIZATION_SIGNATURE_DOMAIN",
    "IssuerAuthorization",
    "IssuerAuthorizationCatalog",
    "issuer_key_identity",
    "load_issuer_authorization_catalog",
)

ISSUER_AUTHORIZATION_SIGNATURE_DOMAIN = b"soai-licensing-issuer-authorization-v1"
_CATALOG_FIELDS = frozenset(("schema_version", "authorizations"))
_AUTHORIZATION_FIELDS = frozenset(
    (
        "schema_version",
        "issuer_key_id",
        "issuer_type",
        "public_key",
        "not_before",
        "not_after",
        "signature_domains",
        "licensed_product_scopes",
        "entitlement_types",
        "max_allowed_personal_deployments",
        "root_signature",
    )
)


def _issuer_rule(
    issuer_type: JSONValue,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], int | None] | None:
    if issuer_type == "term_and_evaluation":
        return (
            (
                "soai-entitlement-commercial-continuity-v1",
                "soai-entitlement-commercial-term-v1",
                "soai-entitlement-evaluation-v1",
                "soai-licensing-status-v1",
            ),
            ("soai_core", "soai_core_and_os", "soai_os"),
            (
                "commercial_continuity",
                "commercial_term",
                "licensing_status",
                "organization_evaluation",
            ),
            None,
        )
    if issuer_type == "personal_os_perpetual":
        return (
            ("soai-entitlement-personal-os-v1",),
            ("soai_os",),
            ("personal_os_perpetual",),
            3,
        )
    if issuer_type == "commercial_perpetual_binding":
        return (
            ("soai-deployment-binding-commercial-perpetual-v1",),
            ("soai_core", "soai_core_and_os", "soai_os"),
            ("commercial_full_perpetual",),
            None,
        )
    if issuer_type == "offline_allocation_request":
        return (
            ("soai-offline-allocation-request-v1",),
            ("soai_core", "soai_core_and_os", "soai_os"),
            ("offline_allocation_request",),
            None,
        )
    return None


@dataclass(frozen=True, slots=True)
class IssuerAuthorization:
    issuer_key_id: str
    issuer_type: str
    public_key: bytes
    not_before: datetime
    not_after: datetime
    signature_domains: tuple[str, ...]
    licensed_product_scopes: tuple[str, ...]
    entitlement_types: tuple[str, ...]
    max_allowed_personal_deployments: int | None
    authorization_bytes: bytes


@dataclass(frozen=True, slots=True)
class IssuerAuthorizationCatalog:
    root_public_key: Ed25519PublicKey
    authorizations: dict[str, IssuerAuthorization]

    def resolve(
        self,
        *,
        issuer_key_id: JSONValue,
        signature_domain: str,
        entitlement_type: str,
        licensed_product_scope: str,
        issued_at: datetime,
        allowed_personal_deployments: int | None,
    ) -> IssuerAuthorization:
        if not isinstance(issuer_key_id, str) or issuer_key_id not in self.authorizations:
            raise ValidationError("Licensing document uses an unknown issuer.")
        authorization = self.authorizations[issuer_key_id]
        _require_authorized(
            authorization,
            signature_domain,
            entitlement_type,
            licensed_product_scope,
            issued_at,
            allowed_personal_deployments,
        )
        return authorization

    def resolve_snapshot(
        self,
        raw_authorization: bytes,
        *,
        issuer_key_id: JSONValue,
        signature_domain: str,
        entitlement_type: str,
        licensed_product_scope: str,
        issued_at: datetime,
        allowed_personal_deployments: int | None,
    ) -> IssuerAuthorization:
        parsed = parse_canonical_licensing_document(raw_authorization)
        authorization = _parse_authorization(parsed, self.root_public_key)
        if authorization.issuer_key_id != issuer_key_id:
            raise ValidationError("Licensing authorization snapshot has the wrong issuer.")
        _require_authorized(
            authorization,
            signature_domain,
            entitlement_type,
            licensed_product_scope,
            issued_at,
            allowed_personal_deployments,
        )
        return authorization


def issuer_key_identity(public_key: bytes) -> str:
    return f"ed25519_{hashlib.sha256(b'ed25519\0' + public_key).hexdigest()}"


def load_issuer_authorization_catalog(
    root_public_key_bytes: bytes,
    raw_catalog: bytes,
) -> IssuerAuthorizationCatalog:
    if len(root_public_key_bytes) != 32:
        raise ValidationError("Licensing root public key must contain exactly 32 bytes.")
    try:
        root_public_key = Ed25519PublicKey.from_public_bytes(root_public_key_bytes)
    except ValueError as exception:
        raise ValidationError("Licensing root public key is invalid.") from exception
    parsed = parse_canonical_licensing_document(raw_catalog)
    catalog = require_json_object(
        parsed,
        label="Licensing issuer catalog",
        build_error=ValidationError,
        invalid_message="Licensing issuer catalog must be an object.",
    )
    require_exact_json_fields(catalog, allowed_fields=_CATALOG_FIELDS, label="Issuer catalog")
    raw_authorizations = catalog.get("authorizations")
    if catalog.get("schema_version") != 1 or not isinstance(raw_authorizations, list):
        raise ValidationError("Licensing issuer catalog contract is invalid.")
    authorizations: dict[str, IssuerAuthorization] = {}
    for raw_authorization in raw_authorizations:
        authorization = _parse_authorization(raw_authorization, root_public_key)
        if authorization.issuer_key_id in authorizations:
            raise ValidationError("Licensing issuer authorization is duplicated.")
        authorizations[authorization.issuer_key_id] = authorization
    return IssuerAuthorizationCatalog(root_public_key, authorizations)


def _parse_authorization(
    value: JSONValue,
    root_public_key: Ed25519PublicKey,
) -> IssuerAuthorization:
    payload = require_json_object(
        value,
        label="Licensing issuer authorization",
        build_error=ValidationError,
        invalid_message="Licensing issuer authorization must be an object.",
    )
    require_exact_json_fields(
        payload,
        allowed_fields=_AUTHORIZATION_FIELDS,
        label="Issuer authorization",
    )
    if payload.get("schema_version") != 1:
        raise ValidationError("Licensing issuer authorization schema is invalid.")
    issuer_type = payload.get("issuer_type")
    rule = _issuer_rule(issuer_type)
    if not isinstance(issuer_type, str) or rule is None:
        raise ValidationError("Licensing issuer authorization type is invalid.")
    public_key_text = payload.get("public_key")
    signature_text = payload.get("root_signature")
    if not isinstance(public_key_text, str) or not isinstance(signature_text, str):
        raise ValidationError("Licensing issuer authorization key material is invalid.")
    public_key = decode_licensing_base64url(public_key_text, expected_bytes=32)
    signature = decode_licensing_base64url(signature_text, expected_bytes=64)
    issuer_key_id = payload.get("issuer_key_id")
    if not isinstance(issuer_key_id, str) or issuer_key_id != issuer_key_identity(public_key):
        raise ValidationError("Licensing issuer key identity is invalid.")
    unsigned = dict(payload)
    del unsigned["root_signature"]
    try:
        root_public_key.verify(
            signature,
            b"".join(
                (
                    ISSUER_AUTHORIZATION_SIGNATURE_DOMAIN,
                    b"\0",
                    canonicalize_licensing_json(unsigned),
                )
            ),
        )
    except InvalidSignature as exception:
        raise ValidationError("Licensing issuer authorization signature is invalid.") from exception
    not_before = parse_licensing_timestamp(payload.get("not_before"), field="not_before")
    not_after = parse_licensing_timestamp(payload.get("not_after"), field="not_after")
    if not_before >= not_after:
        raise ValidationError("Licensing issuer authorization time range is invalid.")
    domains, scopes, entitlement_types, maximum = rule
    if (
        payload.get("signature_domains") != list(domains)
        or payload.get("licensed_product_scopes") != list(scopes)
        or payload.get("entitlement_types") != list(entitlement_types)
        or payload.get("max_allowed_personal_deployments") != maximum
    ):
        raise ValidationError("Licensing issuer authorization scope is invalid.")
    return IssuerAuthorization(
        issuer_key_id,
        issuer_type,
        public_key,
        not_before,
        not_after,
        domains,
        scopes,
        entitlement_types,
        maximum,
        canonicalize_licensing_json(payload),
    )


def _require_authorized(
    authorization: IssuerAuthorization,
    signature_domain: str,
    entitlement_type: str,
    licensed_product_scope: str,
    issued_at: datetime,
    allowed_personal_deployments: int | None,
) -> None:
    maximum = authorization.max_allowed_personal_deployments
    document_authorized = all(
        (
            signature_domain in authorization.signature_domains,
            entitlement_type in authorization.entitlement_types,
            licensed_product_scope in authorization.licensed_product_scopes,
            authorization.not_before <= issued_at <= authorization.not_after,
        )
    )
    personal_capacity_authorized = maximum is None or (
        allowed_personal_deployments is not None and allowed_personal_deployments <= maximum
    )
    if not document_authorized or not personal_capacity_authorized:
        raise ValidationError("Licensing issuer does not authorize this document.")
