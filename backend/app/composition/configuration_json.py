"""SoAI - Configuration data JSON coercion for bootstrap [backend/app/composition/configuration_json.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import normalize_for_json
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("coerce_configuration_data_json",)


def coerce_configuration_data_json(configuration_data: ConfigDict) -> JSONDict:
    configuration_data_json = coerce_json_dict(normalize_for_json(configuration_data))
    if configuration_data_json is None:
        raise ValidationError("Could not coerce configuration data to JSON-compatible format.")
    return configuration_data_json
