"""SoAI - Configuration cloning with field validation [backend/app/config/clone.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import TYPE_CHECKING

from ruamel.yaml.comments import CommentedMap

from core.errors.exceptions import ValidationError
from core.serialization.json import normalize_for_json
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("prepare_cloned_config",)


def prepare_cloned_config(
    source_config: CommentedMap,
    field_overrides: Mapping[str, JSONValue] | None = None,
) -> tuple[JSONDict, JSONDict]:
    source_normalized = coerce_json_dict(normalize_for_json(source_config))
    if source_normalized is None:
        raise ValidationError("Source configuration is not JSON-compatible.")
    cloned_config = copy.deepcopy(source_config)
    if field_overrides:
        for key, value in field_overrides.items():
            cloned_config[key] = value
    normalized = coerce_json_dict(normalize_for_json(cloned_config))
    if normalized is None:
        raise ValidationError("Cloned configuration is not JSON-compatible.")
    return (source_normalized, normalized)
