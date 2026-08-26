"""SoAI - MCP news GDELT operator mappings [backend/mcp/tools/news_operator_mappings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    type OperatorEntry = tuple[str, str, tuple[str, ...]]

__all__ = ("resolve_news_country_operator", "resolve_news_language_operator")

LANGUAGE_OPERATOR_ENTRIES: tuple["OperatorEntry", ...] = (
    ("ar", "arabic", ("ar", "arabic")),
    ("de", "german", ("de", "german")),
    ("en", "english", ("en", "eng", "english")),
    ("es", "spanish", ("es", "spanish")),
    ("fr", "french", ("fr", "french")),
    ("hi", "hindi", ("hi", "hindi")),
    ("it", "italian", ("it", "italian")),
    ("ja", "japanese", ("ja", "japanese")),
    ("ko", "korean", ("ko", "korean")),
    ("nl", "dutch", ("nl", "dutch")),
    ("no", "norwegian", ("no", "norwegian")),
    ("pt", "portuguese", ("pt", "portuguese")),
    ("ru", "russian", ("ru", "russian")),
    ("sv", "swedish", ("sv", "swedish")),
    ("tr", "turkish", ("tr", "turkish")),
    ("zh", "chinese", ("zh", "chinese")),
)
COUNTRY_OPERATOR_ENTRIES: tuple["OperatorEntry", ...] = (
    ("AE", "unitedarabemirates", ("ae", "unitedarabemirates")),
    ("AU", "australia", ("au", "australia")),
    ("BR", "brazil", ("br", "brazil")),
    ("CA", "canada", ("ca", "canada")),
    ("CN", "china", ("cn", "china")),
    ("DE", "germany", ("de", "germany")),
    ("ES", "spain", ("es", "spain")),
    ("FR", "france", ("fr", "france")),
    ("GB", "unitedkingdom", ("gb", "uk", "unitedkingdom")),
    ("IN", "india", ("in", "india")),
    ("IL", "israel", ("il", "israel")),
    ("IT", "italy", ("it", "italy")),
    ("JP", "japan", ("jp", "japan")),
    ("KR", "southkorea", ("kr", "korea", "southkorea")),
    ("MX", "mexico", ("mx", "mexico")),
    ("NL", "netherlands", ("nl", "netherlands")),
    ("NO", "norway", ("no", "norway")),
    ("RU", "russia", ("ru", "russia")),
    ("SA", "saudiarabia", ("sa", "saudiarabia")),
    ("SE", "sweden", ("se", "sweden")),
    ("UA", "ukraine", ("ua", "ukraine")),
    ("US", "unitedstates", ("us", "usa", "unitedstates")),
)


def _lookup_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _resolve_operator(
    value: str,
    entries: tuple["OperatorEntry", ...],
) -> tuple[str, str] | None:
    requested_key = _lookup_key(value)
    for canonical_value, provider_operator, aliases in entries:
        if any(requested_key == _lookup_key(alias) for alias in aliases):
            return canonical_value, provider_operator
    return None


def resolve_news_language_operator(value: str) -> tuple[str, str]:
    resolved = _resolve_operator(value, LANGUAGE_OPERATOR_ENTRIES)
    if resolved is None:
        raise MCPToolError(-32602, f"Unsupported language for news: {value}")
    return resolved


def resolve_news_country_operator(value: str) -> tuple[str, str]:
    resolved = _resolve_operator(value, COUNTRY_OPERATOR_ENTRIES)
    if resolved is None:
        raise MCPToolError(-32602, f"Unsupported country for news: {value}")
    return resolved
