"""SoAI - User-owned account identifier contracts [backend/core/users/account_identifiers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid

__all__ = (
    "CALENDAR_ACCOUNT_ID_PREFIX",
    "CALENDAR_CALENDAR_ID_PREFIX",
    "CALENDAR_EVENT_ID_PREFIX",
    "CALENDAR_REMINDER_ID_PREFIX",
    "EXTERNAL_ACCOUNT_ID_PREFIX",
    "MAIL_ACCOUNT_ID_PREFIX",
    "MAIL_ATTACHMENT_ID_PREFIX",
    "MAIL_FOLDER_ID_PREFIX",
    "MAIL_MESSAGE_ID_PREFIX",
    "build_random_prefixed_identifier",
)

CALENDAR_ACCOUNT_ID_PREFIX = "calacct_"
CALENDAR_CALENDAR_ID_PREFIX = "calcal_"
CALENDAR_EVENT_ID_PREFIX = "calevt_"
CALENDAR_REMINDER_ID_PREFIX = "calrem_"
EXTERNAL_ACCOUNT_ID_PREFIX = "extacct_"
MAIL_ACCOUNT_ID_PREFIX = "mailacct_"
MAIL_ATTACHMENT_ID_PREFIX = "mailatt_"
MAIL_FOLDER_ID_PREFIX = "mailfld_"
MAIL_MESSAGE_ID_PREFIX = "mailmsg_"


def build_random_prefixed_identifier(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex}"
