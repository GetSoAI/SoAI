"""SoAI - Runtime config schema value types [backend/core/config/value_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    type ConfigPrimitive = str | int | float | bool | None | os.PathLike[str]
    type ConfigValue = (
        ConfigPrimitive
        | Mapping[str, ConfigValue]
        | Sequence[ConfigValue]
        | set[ConfigValue]
        | frozenset[ConfigValue]
    )
    type ConfigDict = dict[str, ConfigValue]
else:
    ConfigPrimitive = str | int | float | bool | None | os.PathLike[str]
    ConfigValue = ConfigPrimitive | Mapping[str, ConfigPrimitive] | Sequence[ConfigPrimitive]
    ConfigDict = dict[str, ConfigValue]

__all__: tuple[str, ...] = ()
