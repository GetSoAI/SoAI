"""SoAI - Messaging account mutation validation [backend/database/repositories/users/messaging_account_mutation_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib

from cryptography.fernet import Fernet

from core.errors.exceptions import ValidationError
from core.messaging.account_models import (
    MessagingAccountCreate,
    MessagingAccountUpdate,
    MessagingAuthorizedSender,
)
from core.messaging.account_validation import (
    require_messaging_account_id,
    require_messaging_account_label,
    require_messaging_account_lifecycle_state,
    require_messaging_account_locale,
    require_messaging_credentials,
    require_messaging_platform,
    require_messaging_principal_id,
    validate_messaging_authorized_senders,
    validate_messaging_model_settings,
)
from core.security.secret_crypto import encrypt_required_secret
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict
from core.validation.requirements import require_positive_exact_int
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "normalize_messaging_account_create",
    "normalize_messaging_account_update",
    "prepare_messaging_credentials",
    "require_messaging_generation",
    "require_messaging_revision",
)


def normalize_messaging_account_create(account: MessagingAccountCreate) -> MessagingAccountCreate:
    authorized_senders = validate_messaging_authorized_senders(account.authorized_senders)
    _validate_sender_access(account.accept_messages_from_anyone, authorized_senders)
    return MessagingAccountCreate(
        account_id=require_messaging_account_id(account.account_id),
        platform=require_messaging_platform(account.platform),
        label=require_messaging_account_label(account.label),
        principal_id=require_messaging_principal_id(
            account.principal_id,
            label="Messaging account principal id",
        ),
        principal_label=_normalize_optional_principal(account.principal_label),
        parent_principal_id=_normalize_optional_principal(account.parent_principal_id),
        application_principal_id=_normalize_optional_principal(
            account.application_principal_id,
        ),
        credentials=require_messaging_credentials(account.credentials),
        model_settings=validate_messaging_model_settings(account.model_settings),
        locale=require_messaging_account_locale(account.locale),
        lifecycle_state=require_messaging_account_lifecycle_state(account.lifecycle_state),
        plaintext_secret_replies_enabled=account.plaintext_secret_replies_enabled,
        accept_messages_from_anyone=account.accept_messages_from_anyone,
        authorized_senders=authorized_senders,
    )


def normalize_messaging_account_update(account: MessagingAccountUpdate) -> MessagingAccountUpdate:
    lifecycle_state = require_messaging_account_lifecycle_state(account.lifecycle_state)
    authorized_senders = validate_messaging_authorized_senders(account.authorized_senders)
    _validate_sender_access(account.accept_messages_from_anyone, authorized_senders)
    if lifecycle_state == "deleting":
        raise ValidationError("Messaging account updates cannot enter deleting state.")
    return MessagingAccountUpdate(
        label=require_messaging_account_label(account.label),
        principal_label=_normalize_optional_principal(account.principal_label),
        parent_principal_id=_normalize_optional_principal(account.parent_principal_id),
        application_principal_id=_normalize_optional_principal(
            account.application_principal_id,
        ),
        credentials=(
            require_messaging_credentials(account.credentials)
            if account.credentials is not None
            else None
        ),
        model_settings=validate_messaging_model_settings(account.model_settings),
        locale=require_messaging_account_locale(account.locale),
        lifecycle_state=lifecycle_state,
        plaintext_secret_replies_enabled=account.plaintext_secret_replies_enabled,
        accept_messages_from_anyone=account.accept_messages_from_anyone,
        authorized_senders=authorized_senders,
    )


def prepare_messaging_credentials(
    fernets: tuple[Fernet, ...],
    credentials: JSONDict,
) -> tuple[str, str]:
    credentials_json = serialize_json_compact_stable_strict(credentials)
    encrypted = encrypt_required_secret(
        fernets,
        credentials_json,
        label="Messaging account credentials",
    )
    fingerprint = hashlib.sha256(credentials_json.encode("utf-8")).hexdigest()
    return encrypted, fingerprint


def _validate_sender_access(
    accept_messages_from_anyone: bool,
    authorized_senders: tuple[MessagingAuthorizedSender, ...],
) -> None:
    if accept_messages_from_anyone and authorized_senders:
        raise ValidationError(
            "Messaging unrestricted access cannot include authorized senders.",
        )


def require_messaging_revision(value: int) -> int:
    return require_positive_exact_int(
        value,
        type_message="Messaging account revision must be a positive integer.",
        range_message="Messaging account revision must be a positive integer.",
    )


def require_messaging_generation(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError("Messaging account lifecycle generation is invalid.")
    return value


def _normalize_optional_principal(value: str | None) -> str | None:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        return None
    return require_messaging_principal_id(normalized, label="Messaging parent principal id")
