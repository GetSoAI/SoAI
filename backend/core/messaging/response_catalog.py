"""SoAI - Localized Messaging response catalog [backend/core/messaging/response_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from functools import lru_cache

from core.errors.exceptions import StateError
from core.filesystem.open_files import open_text
from core.serialization.json_parsing import parse_json_dict

__all__ = ("format_messaging_response_text", "resolve_messaging_response_text")


def _catalog_path() -> str:
    return os.path.join(os.path.dirname(__file__), "response_catalog.json")


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, dict[str, str]]:
    with open_text(_catalog_path(), encoding="utf-8", errors="strict") as catalog_file:
        catalog_json = catalog_file.read()
    decoded = parse_json_dict(
        catalog_json,
        field="Messaging response catalog",
    )
    catalog: dict[str, dict[str, str]] = {}
    for locale in ("en", "it"):
        locale_value = decoded.get(locale)
        if not isinstance(locale_value, dict):
            raise StateError("Messaging response catalog locale is invalid.")
        entries: dict[str, str] = {}
        for key, value in locale_value.items():
            if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
                raise StateError("Messaging response catalog entry is invalid.")
            entries[key] = value
        catalog[locale] = entries
    if catalog["en"].keys() != catalog["it"].keys():
        raise StateError("Messaging response catalog locales are not aligned.")
    return catalog


def resolve_messaging_response_text(locale: str, key: str) -> str:
    locale_catalog = _load_catalog().get(locale)
    if locale_catalog is None:
        raise StateError("Messaging response locale is invalid.")
    text = locale_catalog.get(key)
    if text is None:
        raise StateError("Messaging response catalog key is invalid.")
    return text


def format_messaging_response_text(
    locale: str,
    key: str,
    fields: dict[str, str],
) -> str:
    text = resolve_messaging_response_text(locale, key)
    try:
        return text.format_map(fields)
    except (KeyError, ValueError) as exception:
        raise StateError("Messaging response catalog template is invalid.") from exception
