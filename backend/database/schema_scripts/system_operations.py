"""SoAI - Durable database receipt and power operation schema [backend/database/schema_scripts/system_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

__all__ = ("apply_system_operations_schema",)


def apply_system_operations_schema(conn: sqlite3.Connection) -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS database_write_receipts (
            operation_id TEXT PRIMARY KEY,
            committed_at_ms INTEGER NOT NULL CHECK (committed_at_ms >= 0),
            acknowledged_at_ms INTEGER CHECK (
                acknowledged_at_ms IS NULL OR acknowledged_at_ms >= committed_at_ms
            )
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_database_write_receipts_committed_at
            ON database_write_receipts (committed_at_ms)
        """,
        """
        CREATE TABLE IF NOT EXISTS power_operations (
            operation_id TEXT PRIMARY KEY,
            owner_id INTEGER NOT NULL CHECK (owner_id >= 0),
            action TEXT NOT NULL CHECK (
                action IN (
                    'application_restart',
                    'application_shutdown',
                    'host_shutdown',
                    'host_reboot',
                    'host_suspend',
                    'host_hibernate'
                )
            ),
            force INTEGER NOT NULL CHECK (force IN (0, 1)),
            delay_ms INTEGER NOT NULL CHECK (delay_ms BETWEEN 0 AND 86400000),
            accepted_at_ms INTEGER NOT NULL CHECK (accepted_at_ms >= 0),
            execute_at_ms INTEGER NOT NULL CHECK (execute_at_ms >= accepted_at_ms),
            status TEXT NOT NULL CHECK (
                status IN ('scheduled', 'executing', 'completed', 'failed', 'cancelled')
            ),
            claim_owner TEXT,
            lease_expires_at_ms INTEGER CHECK (
                lease_expires_at_ms IS NULL OR lease_expires_at_ms >= 0
            ),
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            dispatch_started_at_ms INTEGER CHECK (
                dispatch_started_at_ms IS NULL OR dispatch_started_at_ms >= accepted_at_ms
            ),
            completed_at_ms INTEGER CHECK (
                completed_at_ms IS NULL OR completed_at_ms >= accepted_at_ms
            ),
            result_code TEXT,
            error_code TEXT,
            active_slot INTEGER UNIQUE CHECK (active_slot IS NULL OR active_slot = 1),
            CHECK (
                (action IN ('application_restart', 'application_shutdown') AND force = 0)
                OR action IN ('host_shutdown', 'host_reboot', 'host_suspend', 'host_hibernate')
            ),
            CHECK (
                (status IN ('scheduled', 'executing') AND active_slot = 1)
                OR (status IN ('completed', 'failed', 'cancelled') AND active_slot IS NULL)
            ),
            CHECK (
                (status = 'scheduled' AND claim_owner IS NULL AND lease_expires_at_ms IS NULL)
                OR status != 'scheduled'
            ),
            CHECK (
                (status = 'executing' AND claim_owner IS NOT NULL AND lease_expires_at_ms IS NOT NULL)
                OR status != 'executing'
            ),
            CHECK (
                (status IN ('completed', 'failed', 'cancelled') AND completed_at_ms IS NOT NULL)
                OR status IN ('scheduled', 'executing')
            )
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_power_operations_due
            ON power_operations (execute_at_ms)
            WHERE active_slot = 1 AND status = 'scheduled'
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_power_operations_completed
            ON power_operations (completed_at_ms)
            WHERE completed_at_ms IS NOT NULL
        """,
    )
    for statement in statements:
        conn.execute(statement)
