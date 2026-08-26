"""SoAI - Messaging export file extension constants [backend/core/files/extensions/messaging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("get_messaging_platform_extension_aliases",)

PLATFORM_WHATSAPP = "whatsapp"
PLATFORM_TELEGRAM = "telegram"
PLATFORM_DISCORD = "discord"
PLATFORM_SIGNAL = "signal"
PLATFORM_FACEBOOK = "facebook"
PLATFORM_MSN = "msn"
PLATFORM_FACEBOOK_ALIAS = "fbmessenger"
PLATFORM_MSN_ALIAS = "msnmsg"

MESSAGING_PLATFORM_IDENTIFIERS = (
    PLATFORM_WHATSAPP,
    PLATFORM_TELEGRAM,
    PLATFORM_DISCORD,
    PLATFORM_SIGNAL,
    PLATFORM_FACEBOOK,
    PLATFORM_MSN,
)

MESSAGING_EXTENSIONS = frozenset(
    (
        *MESSAGING_PLATFORM_IDENTIFIERS,
        PLATFORM_FACEBOOK_ALIAS,
        PLATFORM_MSN_ALIAS,
    ),
)


def get_messaging_platform_extension_aliases() -> dict[str, str]:
    return {
        PLATFORM_FACEBOOK_ALIAS: PLATFORM_FACEBOOK,
        PLATFORM_MSN_ALIAS: PLATFORM_MSN,
    }
