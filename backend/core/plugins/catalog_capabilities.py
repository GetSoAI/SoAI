"""SoAI - Plugin catalog capability predicates [backend/core/plugins/catalog_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict
from core.validation.booleans import parse_bool_flag_with_default

__all__ = ("plugin_record_supports_model_discovery",)


def plugin_record_supports_model_discovery(record: JSONDict) -> bool:
    for key in (
        "local_models",
        "local_resources",
        "supports_external_providers",
        "supports_model_download",
        "supports_model_variant_discovery",
    ):
        if parse_bool_flag_with_default(record.get(key), default=False):
            return True
    return False
