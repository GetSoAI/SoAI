"""SoAI - Default config schema: mail [backend/core/config/default_schema/mail.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_mail_defaults",)


def build_mail_defaults() -> ConfigDict:
    return {
        "MAIL": {
            "SYNC": {
                "ENABLED": True,
                "INTERVAL_SEC": 120,
                "HISTORY": {
                    "MAX_AGE_DAYS": 30,
                    "MAX_MESSAGES_PER_FOLDER": 5000,
                },
                "FOLDERS": {
                    "INCLUDE_SPECIAL_USE": True,
                    "INCLUDE_NAMES": [],
                    "EXCLUDE_NAMES": ["Junk", "Spam"],
                },
            },
            "LIMITS": {
                "LIST_DEFAULT": 50,
                "LIST_MAX": 200,
                "READ_MAX_CHARS": 50_000,
                "SNIPPET_MAX_CHARS": 500,
                "ATTACHMENT_MAX_BYTES": 25_000_000,
            },
            "TIMEOUTS": {
                "CONNECT_SEC": 30.0,
                "COMMAND_SEC": 30.0,
            },
            "CONCURRENCY": {
                "MAX_CONCURRENT_PER_ACCOUNT": 2,
            },
            "BACKFILL": {
                "BATCH_LIMIT_DEFAULT": 200,
                "BATCH_LIMIT_MAX": 1000,
            },
            "REMOTE_SEARCH": {
                "LIMIT_DEFAULT": 50,
                "LIMIT_MAX": 200,
                "REQUIRE_NARROWING_FILTER": True,
                "TEXT_REQUIRES_TIME_BOUND": True,
            },
        },
    }
