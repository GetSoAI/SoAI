"""SoAI - Offline mode config parsing helpers (stdlib-only) [backend/core/bootstrap/offline_mode.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

__all__ = (
    "parse_bool_literal",
    "read_yaml_boolean_key",
)

_OFFLINE_TRUE_LITERALS = frozenset(("1", "true", "yes", "on", "y", "t"))
_OFFLINE_FALSE_LITERALS = frozenset(("0", "false", "no", "off", "n", "f"))


def parse_bool_literal(value: str) -> bool | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.startswith("!!bool") or cleaned.startswith("!bool"):
        parts = cleaned.split(None, 1)
        if len(parts) == 1:
            return None
        cleaned = parts[1].strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    normalized = cleaned.lower()
    if normalized in _OFFLINE_TRUE_LITERALS:
        return True
    if normalized in _OFFLINE_FALSE_LITERALS:
        return False
    return None


def read_yaml_boolean_key(config_path: str, *, key: str) -> bool | None:
    if not os.path.exists(config_path):
        return None
    parts = [part for part in key.split(".") if part]
    if not parts:
        return None
    resolved: bool | None = None
    key_stack: list[str] = []
    with open(config_path, encoding="utf-8", errors="strict") as config_file:
        for line in config_file:
            stripped = line.lstrip(" ")
            if not stripped or stripped.startswith("#"):
                continue
            indent_width = len(line) - len(stripped)
            if indent_width % 2 != 0:
                continue
            level = indent_width // 2
            key_text, sep, raw_value = stripped.partition(":")
            if not sep:
                continue
            segment = key_text.strip()
            if len(parts) == 1:
                if segment != parts[0]:
                    continue
                value_text = raw_value.strip().split("#", 1)[0].strip()
                if not value_text:
                    raise ValueError(f"{key} must be set to a boolean value in config.yaml.")
                parsed = parse_bool_literal(value_text)
                if parsed is None:
                    raise ValueError(f"{key} must be a boolean value. Got: {value_text!r}")
                if resolved is not None and resolved != parsed:
                    raise ValueError(f"{key} is defined multiple times with conflicting values.")
                resolved = parsed
                continue
            if len(key_stack) > level:
                key_stack = key_stack[:level]
            if level >= len(parts):
                continue
            if segment != parts[level]:
                continue
            if len(key_stack) == level:
                key_stack.append(segment)
            else:
                key_stack[level] = segment
            if key_stack != parts[: level + 1]:
                continue
            raw_value = raw_value.strip()
            if level + 1 != len(parts):
                continue
            if not raw_value:
                raise ValueError(f"{key} must be set to a boolean value in config.yaml.")
            value_text = raw_value.split("#", 1)[0].strip()
            parsed = parse_bool_literal(value_text)
            if parsed is None:
                raise ValueError(f"{key} must be a boolean value. Got: {value_text!r}")
            if resolved is not None and resolved != parsed:
                raise ValueError(f"{key} is defined multiple times with conflicting values.")
            resolved = parsed
    return resolved
