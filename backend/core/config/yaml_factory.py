"""SoAI - Central YAML factory with round-trip preservation [backend/core/config/yaml_factory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from ruamel.yaml import YAML
from ruamel.yaml.nodes import Node
from ruamel.yaml.representer import RoundTripRepresenter
from ruamel.yaml.scalarint import ScalarInt

__all__ = ("build_roundtrip_yaml",)

_GROUPED_INTEGER_MINIMUM_ABS = 1_000_000
_GROUPED_INTEGER_UNDERSCORE = (3, False, False)


def _represent_readable_integer(representer: RoundTripRepresenter, value: int) -> Node:
    if abs(value) >= _GROUPED_INTEGER_MINIMUM_ABS:
        grouped_value = ScalarInt(value, underscore=_GROUPED_INTEGER_UNDERSCORE)
        grouped_node: Node = representer.represent_data(grouped_value)
        return grouped_node
    integer_node: Node = representer.represent_int(value)
    return integer_node


def build_roundtrip_yaml() -> YAML:
    yaml_instance = YAML()
    yaml_instance.preserve_quotes = True
    yaml_instance.indent(mapping=2, sequence=4, offset=2)
    yaml_instance.width = 160
    yaml_instance.representer.add_representer(int, _represent_readable_integer)
    return yaml_instance
