"""SoAI - Runtime environment flag readers [backend/core/runtime/environment_flags.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.validation.booleans import parse_bool_flag_or_none

__all__ = (
    "is_soai_bootstrap_verbose",
    "is_soai_gui_launched",
    "is_soai_no_browser",
    "is_soai_stay_offline",
    "read_env_bool_or_none",
    "read_env_flag_is_one",
    "read_env_stripped_flag_is_one",
)


def read_env_flag_is_one(name: str) -> bool:
    return os.environ.get(name, "") == "1"


def read_env_stripped_flag_is_one(name: str) -> bool:
    return os.environ.get(name, "0").strip() == "1"


def read_env_bool_or_none(name: str) -> bool | None:
    return parse_bool_flag_or_none(os.environ.get(name, ""))


def is_soai_no_browser() -> bool:
    return bool(os.environ.get("SOAI_NO_BROWSER", ""))


def is_soai_gui_launched() -> bool:
    return bool(os.environ.get("SOAI_GUI_LAUNCHED", ""))


def is_soai_bootstrap_verbose() -> bool:
    return read_env_flag_is_one("SOAI_BOOTSTRAP_VERBOSE")


def is_soai_stay_offline() -> bool:
    return read_env_stripped_flag_is_one("SOAI_STAY_OFFLINE")
