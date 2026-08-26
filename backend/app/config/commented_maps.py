"""SoAI - YAML CommentedMap utilities [backend/app/config/commented_maps.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from ruamel.yaml.comments import CommentedMap

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("build_commented_map",)


def build_commented_map(configuration_data: Mapping[str, JSONValue]) -> CommentedMap:
    if not isinstance(configuration_data, Mapping):
        raise ValidationError("Configuration payload must be a mapping.")
    commented_map = CommentedMap()
    for key, value in configuration_data.items():
        commented_map[key] = value
    return commented_map
