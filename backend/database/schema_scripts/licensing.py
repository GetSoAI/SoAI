"""SoAI - Licensing V1 persistence schema [backend/database/schema_scripts/licensing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.licensing.operation_outcomes import licensing_operation_terminal_codes
from core.validation.epoch import EPOCH_MS_MAX, EPOCH_MS_MIN
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from database.sql.script import execute_sql_script


def build_licensing_schema_sql() -> str:
    terminal_codes = ", ".join(f"'{code}'" for code in sorted(licensing_operation_terminal_codes()))
    return f"""
        CREATE TABLE IF NOT EXISTS licensing_wizard_draft (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            edition TEXT NOT NULL CHECK(edition IN ('soai-core', 'soai-os')),
            revision INTEGER NOT NULL CHECK(revision BETWEEN 0 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            accepted_license_fingerprint TEXT CHECK(
                accepted_license_fingerprint IS NULL OR
                substr(accepted_license_fingerprint, 1, 7) = 'sha256:' AND
                substr(accepted_license_fingerprint, 8) NOT GLOB '*[^a-f0-9]*' AND
                length(accepted_license_fingerprint) = 71),
            accepted_license_at_ms INTEGER CHECK(
                accepted_license_at_ms IS NULL OR
                accepted_license_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            declaration TEXT CHECK(declaration IS NULL OR declaration IN ('personal', 'organization_commercial')),
            attestation_revision TEXT CHECK(
                attestation_revision IS NULL OR
                attestation_revision = 'personal-use-attestation-v1'),
            attestation_confirmed_at_ms INTEGER CHECK(
                attestation_confirmed_at_ms IS NULL OR
                attestation_confirmed_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            evaluation_fingerprint TEXT CHECK(
                evaluation_fingerprint IS NULL OR
                substr(evaluation_fingerprint, 1, 7) = 'sha256:' AND
                substr(evaluation_fingerprint, 8) NOT GLOB '*[^a-f0-9]*' AND
                length(evaluation_fingerprint) = 71),
            evaluation_acknowledged_at_ms INTEGER CHECK(
                evaluation_acknowledged_at_ms IS NULL OR
                evaluation_acknowledged_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            selected_access_flow TEXT CHECK(selected_access_flow IS NULL OR selected_access_flow IN (
                'evaluation', 'online_activation', 'offline_activation')),
            resume_step TEXT NOT NULL CHECK(resume_step IN (
                'welcome', 'license', 'use', 'product_access', 'account', 'complete')),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms BETWEEN created_at_ms AND {EPOCH_MS_MAX}),
            CHECK((accepted_license_fingerprint IS NULL) = (accepted_license_at_ms IS NULL)),
            CHECK((attestation_revision IS NULL) = (attestation_confirmed_at_ms IS NULL)),
            CHECK((evaluation_fingerprint IS NULL) = (evaluation_acknowledged_at_ms IS NULL))
        ) STRICT;

        CREATE TABLE IF NOT EXISTS licensing_deployment_identity (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            public_key BLOB NOT NULL CHECK(length(public_key) = 32),
            encrypted_private_key BLOB NOT NULL CHECK(length(encrypted_private_key) > 32),
            key_algorithm TEXT NOT NULL CHECK(key_algorithm = 'ed25519'),
            key_version INTEGER NOT NULL CHECK(key_version = 1),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX})
        ) STRICT;

        CREATE TABLE IF NOT EXISTS licensing_verified_clock (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            verified_time_high_water_ms INTEGER NOT NULL CHECK(
                verified_time_high_water_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX})
        ) STRICT;

        CREATE TABLE IF NOT EXISTS licensing_operations (
            operation_id TEXT PRIMARY KEY CHECK(
                length(operation_id) = 36 AND operation_id = lower(operation_id) AND
                substr(operation_id, 9, 1) = '-' AND substr(operation_id, 14, 1) = '-' AND
                substr(operation_id, 15, 1) = '4' AND substr(operation_id, 19, 1) = '-' AND
                substr(operation_id, 20, 1) IN ('8', '9', 'a', 'b') AND
                substr(operation_id, 24, 1) = '-' AND
                length(replace(operation_id, '-', '')) = 32 AND
                replace(operation_id, '-', '') NOT GLOB '*[^a-f0-9]*'),
            operation_type TEXT NOT NULL CHECK(operation_type IN (
                'evaluation', 'os-evaluation-conversion', 'os-evaluation-reversion',
                'activation', 'commercial-conversion', 'deployment-reclassification',
                'term-renewal', 'operation-reconciliation', 'deactivation',
                'offline_export', 'offline_import')),
            state TEXT NOT NULL CHECK(state IN (
                'prepared', 'sending', 'outcome_unknown', 'reconciling', 'retry_wait',
                'succeeded', 'failed', 'cancelled')),
            idempotency_key TEXT CHECK(
                idempotency_key IS NULL OR
                length(idempotency_key) BETWEEN 16 AND 128 AND
                idempotency_key NOT GLOB '*[^A-Za-z0-9_-]*'),
            parent_operation_id TEXT REFERENCES licensing_operations(operation_id),
            request_digest TEXT NOT NULL CHECK(
                substr(request_digest, 1, 7) = 'sha256:' AND
                substr(request_digest, 8) NOT GLOB '*[^a-f0-9]*' AND
                length(request_digest) = 71),
            request_nonce BLOB CHECK(request_nonce IS NULL OR length(request_nonce) = 32),
            canonical_request BLOB CHECK(
                canonical_request IS NULL OR length(canonical_request) BETWEEN 2 AND 16384),
            response_content BLOB CHECK(
                response_content IS NULL OR length(response_content) BETWEEN 2 AND 65536),
            edition TEXT NOT NULL CHECK(edition IN ('soai-core', 'soai-os')),
            licensed_product_scope TEXT NOT NULL CHECK(licensed_product_scope IN (
                'soai_core', 'soai_os', 'soai_core_and_os')),
            instance_id TEXT NOT NULL CHECK(
                length(instance_id) = 36 AND instance_id = lower(instance_id) AND
                substr(instance_id, 9, 1) = '-' AND substr(instance_id, 14, 1) = '-' AND
                substr(instance_id, 15, 1) = '4' AND substr(instance_id, 19, 1) = '-' AND
                substr(instance_id, 20, 1) IN ('8', '9', 'a', 'b') AND
                substr(instance_id, 24, 1) = '-' AND
                length(replace(instance_id, '-', '')) = 32 AND
                replace(instance_id, '-', '') NOT GLOB '*[^a-f0-9]*'),
            activation_id TEXT CHECK(
                activation_id IS NULL OR length(activation_id) BETWEEN 16 AND 128 AND
                activation_id NOT GLOB '*[^A-Za-z0-9_-]*'),
            deployment_id TEXT CHECK(
                deployment_id IS NULL OR length(deployment_id) BETWEEN 16 AND 128 AND
                deployment_id NOT GLOB '*[^A-Za-z0-9_-]*'),
            deactivation_reason TEXT CHECK(
                deactivation_reason IS NULL OR deactivation_reason IN (
                    'rehost', 'retired', 'disaster_recovery', 'other')),
            attempt_count INTEGER NOT NULL CHECK(attempt_count BETWEEN 0 AND 1000000),
            last_attempt_at_ms INTEGER CHECK(
                last_attempt_at_ms IS NULL OR last_attempt_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            next_retry_at_ms INTEGER CHECK(
                next_retry_at_ms IS NULL OR next_retry_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            terminal_code TEXT CHECK(
                terminal_code IS NULL OR terminal_code IN ({terminal_codes})),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms BETWEEN created_at_ms AND {EPOCH_MS_MAX}),
            CHECK((state IN ('retry_wait', 'outcome_unknown')) = (next_retry_at_ms IS NOT NULL)),
            CHECK(
                (operation_type NOT IN ('offline_export', 'offline_import'))
                = (idempotency_key IS NOT NULL)),
            CHECK((operation_type = 'offline_import') = (parent_operation_id IS NOT NULL)),
            CHECK((operation_type = 'deactivation') = (deactivation_reason IS NOT NULL)),
            CHECK(canonical_request IS NULL),
            CHECK(
                (operation_type NOT IN ('offline_export', 'offline_import'))
                = (request_nonce IS NOT NULL)),
            CHECK(
                (state = 'failed' AND terminal_code IS NOT NULL)
                OR (state = 'succeeded' AND terminal_code IS NULL)
                OR (state NOT IN ('failed', 'succeeded') AND terminal_code IS NULL)
            ),
            CHECK(
                operation_type IN ('offline_export', 'offline_import')
                OR (state = 'succeeded') = (response_content IS NOT NULL))
        ) STRICT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_licensing_operation_one_active
            ON licensing_operations((1))
            WHERE state IN ('prepared', 'sending', 'outcome_unknown', 'reconciling', 'retry_wait');

        CREATE TABLE IF NOT EXISTS licensing_deployment_transitions (
            operation_id TEXT PRIMARY KEY REFERENCES licensing_operations(operation_id),
            instance_id TEXT NOT NULL CHECK(
                length(instance_id) = 36 AND instance_id = lower(instance_id) AND
                substr(instance_id, 9, 1) = '-' AND substr(instance_id, 14, 1) = '-' AND
                substr(instance_id, 15, 1) = '4' AND substr(instance_id, 19, 1) = '-' AND
                substr(instance_id, 20, 1) IN ('8', '9', 'a', 'b') AND
                substr(instance_id, 24, 1) = '-' AND
                length(replace(instance_id, '-', '')) = 32 AND
                replace(instance_id, '-', '') NOT GLOB '*[^a-f0-9]*'),
            deployment_id TEXT NOT NULL CHECK(
                length(deployment_id) BETWEEN 16 AND 128 AND
                deployment_id NOT GLOB '*[^A-Za-z0-9_-]*'),
            old_public_key BLOB NOT NULL UNIQUE CHECK(length(old_public_key) = 32),
            new_public_key BLOB NOT NULL UNIQUE CHECK(length(new_public_key) = 32),
            canonical_transition BLOB NOT NULL CHECK(
                length(canonical_transition) BETWEEN 2 AND 16384),
            completed_at_ms INTEGER NOT NULL CHECK(
                completed_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            CHECK(old_public_key != new_public_key)
        ) STRICT;

        CREATE TABLE IF NOT EXISTS licensing_offline_requests (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            operation_id TEXT NOT NULL UNIQUE REFERENCES licensing_operations(operation_id),
            draft_revision INTEGER NOT NULL CHECK(
                draft_revision BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            edition TEXT NOT NULL CHECK(edition IN ('soai-core', 'soai-os')),
            licensed_product_scope TEXT NOT NULL CHECK(licensed_product_scope IN (
                'soai_core', 'soai_os', 'soai_core_and_os')),
            instance_id TEXT NOT NULL CHECK(
                length(instance_id) = 36 AND instance_id = lower(instance_id) AND
                substr(instance_id, 9, 1) = '-' AND substr(instance_id, 14, 1) = '-' AND
                substr(instance_id, 15, 1) = '4' AND substr(instance_id, 19, 1) = '-' AND
                substr(instance_id, 20, 1) IN ('8', '9', 'a', 'b') AND
                substr(instance_id, 24, 1) = '-' AND
                length(replace(instance_id, '-', '')) = 32 AND
                replace(instance_id, '-', '') NOT GLOB '*[^a-f0-9]*'),
            deployment_public_key BLOB NOT NULL CHECK(length(deployment_public_key) = 32),
            request_digest TEXT NOT NULL CHECK(
                substr(request_digest, 1, 7) = 'sha256:' AND
                substr(request_digest, 8) NOT GLOB '*[^a-f0-9]*' AND
                length(request_digest) = 71),
            canonical_content BLOB NOT NULL CHECK(length(canonical_content) BETWEEN 2 AND 16384),
            created_at_ms INTEGER NOT NULL CHECK(
                created_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            fulfilled_at_ms INTEGER CHECK(
                fulfilled_at_ms IS NULL OR
                fulfilled_at_ms BETWEEN created_at_ms AND {EPOCH_MS_MAX})
        ) STRICT;

        CREATE TABLE IF NOT EXISTS licensing_documents (
            document_digest TEXT PRIMARY KEY CHECK(
                substr(document_digest, 1, 7) = 'sha256:' AND
                substr(document_digest, 8) NOT GLOB '*[^a-f0-9]*' AND
                length(document_digest) = 71),
            canonical_content BLOB NOT NULL CHECK(length(canonical_content) BETWEEN 2 AND 65536),
            document_type TEXT NOT NULL CHECK(document_type IN ('entitlement', 'licensing_status', 'offline_entitlement')),
            entitlement_type TEXT CHECK(entitlement_type IS NULL OR entitlement_type IN (
                'organization_evaluation', 'commercial_term', 'commercial_continuity',
                'personal_os_perpetual', 'commercial_full_perpetual')),
            entitlement_id TEXT CHECK(
                entitlement_id IS NULL OR length(entitlement_id) BETWEEN 16 AND 128 AND
                entitlement_id NOT GLOB '*[^A-Za-z0-9_-]*'),
            license_id TEXT CHECK(
                license_id IS NULL OR length(license_id) BETWEEN 16 AND 128 AND
                license_id NOT GLOB '*[^A-Za-z0-9_-]*'),
            deployment_id TEXT NOT NULL CHECK(
                length(deployment_id) BETWEEN 16 AND 128 AND
                deployment_id NOT GLOB '*[^A-Za-z0-9_-]*'),
            generation INTEGER NOT NULL CHECK(generation BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            disposition TEXT NOT NULL CHECK(disposition IN ('active', 'pending', 'historical')),
            issuer_authorization_snapshot BLOB NOT NULL CHECK(length(issuer_authorization_snapshot) BETWEEN 2 AND 65536),
            accepted_at_ms INTEGER NOT NULL CHECK(accepted_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            CHECK((document_type = 'licensing_status') = (entitlement_type IS NULL))
        ) STRICT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_licensing_document_one_active
            ON licensing_documents(
                CASE WHEN document_type = 'licensing_status' THEN 'status' ELSE 'entitlement' END
            ) WHERE disposition = 'active';
        CREATE UNIQUE INDEX IF NOT EXISTS idx_licensing_document_one_pending
            ON licensing_documents((1)) WHERE disposition = 'pending';
        CREATE UNIQUE INDEX IF NOT EXISTS idx_licensing_document_generation
            ON licensing_documents(deployment_id, generation);

        CREATE TABLE IF NOT EXISTS licensing_acceptance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER REFERENCES webui_users(id),
            event_type TEXT NOT NULL CHECK(event_type IN ('license_acceptance', 'declaration', 'evaluation_acknowledgement')),
            edition TEXT NOT NULL CHECK(edition IN ('soai-core', 'soai-os')),
            fingerprint TEXT CHECK(
                fingerprint IS NULL OR substr(fingerprint, 1, 7) = 'sha256:' AND
                substr(fingerprint, 8) NOT GLOB '*[^a-f0-9]*' AND
                length(fingerprint) = 71),
            declaration TEXT CHECK(declaration IS NULL OR declaration IN ('personal', 'organization_commercial')),
            occurred_at_ms INTEGER NOT NULL CHECK(occurred_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            CHECK(
                (event_type IN ('license_acceptance', 'evaluation_acknowledgement') AND fingerprint IS NOT NULL)
                OR (event_type = 'declaration' AND declaration IS NOT NULL))
        ) STRICT;
    """


def apply_licensing_schema(connection: sqlite3.Connection) -> None:
    execute_sql_script(connection, build_licensing_schema_sql())


__all__ = ("apply_licensing_schema", "build_licensing_schema_sql")
