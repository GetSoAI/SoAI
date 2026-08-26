"""SoAI - Instance identity resolution and discovery payload contract [backend/core/meta/instance_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict
from uuid import uuid4

from core.errors.exceptions import ValidationError
from core.licensing.identifiers import require_canonical_uuid4
from core.licensing.protocols import LicensingBindingQueryProtocol
from core.meta.version import __version__
from core.plugins.protocols_database import DatabasePluginsProtocol

__all__ = (
    "INSTANCE_ID_SETTING_KEY",
    "INSTANCE_NAME_MAX_LENGTH",
    "INSTANCE_NAME_SETTING_KEY",
    "SOAI_PRODUCT_MARKER",
    "InstanceIdentity",
    "InstanceIdentityPayload",
    "build_instance_identity_payload",
    "normalize_instance_name",
    "persist_instance_name",
    "resolve_instance_identity",
)

SOAI_PRODUCT_MARKER = "soai"
INSTANCE_ID_SETTING_KEY = "instance.id"
INSTANCE_NAME_SETTING_KEY = "instance.name"
INSTANCE_NAME_MAX_LENGTH = 64


@dataclass(frozen=True, slots=True)
class InstanceIdentity:
    instance_id: str
    instance_name: str | None


class InstanceIdentityPayload(TypedDict):
    product: str
    version: str
    instance_id: str
    instance_name: str | None


def normalize_instance_name(raw_name: str | None) -> str | None:
    if raw_name is None:
        return None
    normalized = raw_name.strip()
    if not normalized:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValidationError("Instance name must not contain control characters.")
    if len(normalized) > INSTANCE_NAME_MAX_LENGTH:
        raise ValidationError(
            f"Instance name must be at most {INSTANCE_NAME_MAX_LENGTH} characters.",
        )
    return normalized


def build_instance_identity_payload(identity: InstanceIdentity) -> InstanceIdentityPayload:
    require_canonical_uuid4(identity.instance_id)
    return {
        "product": SOAI_PRODUCT_MARKER,
        "version": __version__,
        "instance_id": identity.instance_id,
        "instance_name": identity.instance_name,
    }


async def resolve_instance_identity(
    database_plugins: DatabasePluginsProtocol,
    licensing_binding: LicensingBindingQueryProtocol,
) -> InstanceIdentity:
    instance_id = await _resolve_instance_id(database_plugins, licensing_binding)
    stored_name = await database_plugins.get_system_setting(INSTANCE_NAME_SETTING_KEY)
    instance_name = normalize_instance_name(stored_name) if isinstance(stored_name, str) else None
    return InstanceIdentity(instance_id=instance_id, instance_name=instance_name)


async def persist_instance_name(
    database_plugins: DatabasePluginsProtocol,
    raw_name: str | None,
) -> str | None:
    instance_name = normalize_instance_name(raw_name)
    await database_plugins.set_system_setting(
        INSTANCE_NAME_SETTING_KEY,
        instance_name,
    )
    return instance_name


async def _resolve_instance_id(
    database_plugins: DatabasePluginsProtocol,
    licensing_binding: LicensingBindingQueryProtocol,
) -> str:
    stored_id = await database_plugins.get_system_setting(INSTANCE_ID_SETTING_KEY)
    if isinstance(stored_id, str):
        valid_stored_id = _valid_instance_id(stored_id)
        if valid_stored_id is not None:
            return valid_stored_id
    generated_id = str(uuid4())
    return require_canonical_uuid4(await licensing_binding.resolve_instance_id(generated_id))


def _valid_instance_id(value: str) -> str | None:
    try:
        return require_canonical_uuid4(value)
    except ValidationError:
        return None
