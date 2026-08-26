"""SoAI - Log palette utilities [backend/core/logging/palette.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("get_palette_colors",)

ANSI_GREY = "\x1b[90m"
ANSI_ORANGE = "\x1b[93m"
ANSI_GREEN = "\x1b[92m"
ANSI_BLUE = "\x1b[94m"
ANSI_RED = "\x1b[91m"
ANSI_WHITE = "\x1b[97m"
ANSI_AMBER = "\x1b[38;5;208m"
ANSI_TANGERINE = "\x1b[38;5;214m"
ANSI_GRAPHITE = "\x1b[38;5;240m"
ANSI_SILVER = "\x1b[37m"
ANSI_ASH = "\x1b[38;5;245m"
ANSI_CHARCOAL = "\x1b[38;5;238m"
ANSI_PEWTER = "\x1b[38;5;249m"
ANSI_PLATINUM = "\x1b[38;5;253m"
ANSI_EMERALD = "\x1b[38;5;35m"
ANSI_VERDANT = "\x1b[38;5;70m"
ANSI_TEAL = "\x1b[38;5;37m"
ANSI_SKY = "\x1b[38;5;39m"
ANSI_LILAC = "\x1b[38;5;147m"
ANSI_ROSE = "\x1b[38;5;203m"
ANSI_RUBY = "\x1b[38;5;196m"
ANSI_COPPER = "\x1b[38;5;166m"
ANSI_GOLD = "\x1b[38;5;220m"
ANSI_LEMON = "\x1b[38;5;227m"
ANSI_LIME = "\x1b[38;5;118m"
ANSI_TIMESTAMP = "\x1b[38;5;246m"
ANSI_COMPONENT = "\x1b[38;5;215m"


def get_palette_colors() -> dict[str, str]:
    return {
        "grey": ANSI_GREY,
        "orange": ANSI_ORANGE,
        "green": ANSI_GREEN,
        "blue": ANSI_BLUE,
        "red": ANSI_RED,
        "white": ANSI_WHITE,
        "amber": ANSI_AMBER,
        "tangerine": ANSI_TANGERINE,
        "graphite": ANSI_GRAPHITE,
        "silver": ANSI_SILVER,
        "ash": ANSI_ASH,
        "charcoal": ANSI_CHARCOAL,
        "pewter": ANSI_PEWTER,
        "platinum": ANSI_PLATINUM,
        "emerald": ANSI_EMERALD,
        "verdant": ANSI_VERDANT,
        "teal": ANSI_TEAL,
        "sky": ANSI_SKY,
        "lilac": ANSI_LILAC,
        "rose": ANSI_ROSE,
        "ruby": ANSI_RUBY,
        "copper": ANSI_COPPER,
        "gold": ANSI_GOLD,
        "lemon": ANSI_LEMON,
        "lime": ANSI_LIME,
        "timestamp": ANSI_TIMESTAMP,
        "component": ANSI_COMPONENT,
    }
