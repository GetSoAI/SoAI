"""SoAI - Database repository for external provider CRUD [backend/database/repositories/plugins/providers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.errors.exceptions import StateError, ValidationError
from core.models.external_provider_record import normalize_external_provider_name
from core.state.errors import DuplicateProviderError
from core.timing.epoch import epoch_ms
from database.core.query_execution import (
    sync_fetch_one_as_dict,
)
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.plugins.provider_mutation_validation import (
    require_provider_validation_state,
)
from database.repositories.plugins.provider_read_queries import (
    sync_get_external_provider,
)
from database.repositories.plugins.provider_status_outbox import (
    enqueue_provider_status_event,
)

if TYPE_CHECKING:
    from core.models.external_provider_record import ExternalProviderInternalRecord

__all__ = ()


def sync_upsert_plugin_managed_provider(
    conn: sqlite3.Connection,
    fernet: tuple[Fernet, ...],
    plugin_name: str,
    provider_id: str,
    name: str,
    url: str,
) -> ExternalProviderInternalRecord | None:
    normalized_provider_id = provider_id.strip() if isinstance(provider_id, str) else ""
    normalized_plugin_name = plugin_name.strip() if isinstance(plugin_name, str) else ""
    normalized_name = name.strip() if isinstance(name, str) else ""
    canonical_name = normalize_external_provider_name(normalized_name)
    normalized_url = url.strip() if isinstance(url, str) else ""
    if not normalized_provider_id or not normalized_plugin_name:
        raise ValidationError("Provider ID and plugin name are required.")
    if not normalized_name:
        raise ValidationError("Provider name is required.")
    if not normalized_url:
        raise ValidationError("Provider URL is required.")
    try:
        existing = sync_fetch_one_as_dict(
            conn.execute(
                "SELECT id FROM models_external_providers WHERE id = ?",
                (normalized_provider_id,),
            ),
        )
        if existing:
            conn.execute(
                """UPDATE models_external_providers
                SET plugin_name = ?, name = ?, canonical_name = ?, api_url = ?, revision = revision + 1
                WHERE id = ?""",
                (
                    normalized_plugin_name,
                    normalized_name,
                    canonical_name,
                    normalized_url,
                    normalized_provider_id,
                ),
            )
        else:
            conn.execute(
                "INSERT INTO models_external_providers (id, plugin_name, name, canonical_name, api_url, api_key, models_filter, context_window_tokens, created_at_ms, last_status) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?, 'VALIDATING')",
                (
                    normalized_provider_id,
                    normalized_plugin_name,
                    normalized_name,
                    canonical_name,
                    normalized_url,
                    epoch_ms(),
                ),
            )
        return sync_get_external_provider(conn, fernet, normalized_provider_id, decrypt_key=False)
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        if constraint_type == "unique":
            raise DuplicateProviderError(
                f"A provider for plugin '{normalized_plugin_name}' with URL '{normalized_url}' already exists.",
            ) from exception
        if constraint_type == "foreign_key":
            raise ValidationError(
                f"Plugin '{normalized_plugin_name}' does not exist.",
            ) from exception
        if constraint_type in ("check", "not_null"):
            raise ValidationError(
                f"Invalid provider configuration: constraint violation on {detail or 'unknown field'}.",
            ) from exception
        raise StateError(f"Database constraint violation: {exception}") from exception


def sync_update_provider_status(
    conn: sqlite3.Connection,
    provider_id: str,
    status: str,
    error: str | None = None,
) -> bool:
    checked_at_ms = epoch_ms()
    normalized_status, normalized_error, validated_at_ms = require_provider_validation_state(
        status,
        error,
        checked_at_ms,
    )
    row = conn.execute(
        "SELECT plugin_name, revision FROM models_external_providers WHERE id = ?",
        (provider_id,),
    ).fetchone()
    if row is None:
        return False
    new_revision = row["revision"] + 1
    updated = conn.execute(
        """UPDATE models_external_providers
        SET last_status = ?, last_error = ?, last_checked_at_ms = ?, revision = ?
        WHERE id = ? AND revision = ?""",
        (
            normalized_status,
            normalized_error,
            validated_at_ms,
            new_revision,
            provider_id,
            row["revision"],
        ),
    ).rowcount
    if updated != 1:
        raise StateError("Provider revision changed during status persistence.")
    enqueue_provider_status_event(
        conn,
        row["plugin_name"],
        provider_id,
        normalized_status,
        normalized_error,
        validated_at_ms,
    )
    return True
