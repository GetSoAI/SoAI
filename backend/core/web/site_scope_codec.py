"""SoAI - Site scope JSON parsing and serialization helpers [backend/core/web/site_scope_codec.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONDict, JSONValue
from core.web.site_scope import SiteScope

__all__ = (
    "coerce_site_scope_json_dict",
    "parse_site_scope_json_str",
    "parse_site_scope_obj",
    "serialize_site_scope_json",
)


def serialize_site_scope_json(scope: SiteScope) -> str:
    return serialize_json_compact_stable_strict(coerce_site_scope_json_dict(scope))


def coerce_site_scope_json_dict(scope: SiteScope) -> JSONDict:
    scope_type = scope.get("scope_type")
    if scope_type == "origin":
        origin = scope.get("origin")
        if isinstance(origin, str) and origin.strip():
            return {
                "scope_type": "origin",
                "origin": origin.strip().lower(),
            }
    raise ValueError("site scope shape is invalid.")


def parse_site_scope_json_str(value: str) -> SiteScope:
    try:
        decoded = parse_json_value(value)
    except ValidationError as exception:
        raise ValueError("site scope JSON is not valid JSON.") from exception
    scope = parse_site_scope_obj(decoded)
    if scope is None:
        raise ValueError("site scope JSON shape is invalid.")
    return scope


def parse_site_scope_obj(value: JSONValue) -> SiteScope | None:
    if not isinstance(value, dict):
        return None
    scope_type_value = value.get("scope_type")
    if scope_type_value == "origin":
        origin_value = value.get("origin")
        if not isinstance(origin_value, str) or not origin_value.strip():
            return None
        return {
            "scope_type": "origin",
            "origin": origin_value.strip().lower(),
        }
    return None
