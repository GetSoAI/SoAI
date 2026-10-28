"""SoAI - Durable bulk backend update child identity [backend/core/plugins/backend_update_child.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.mutations.identifiers import require_mutation_request_id
from core.plugins.backend_variant_ids import require_backend_variant_id
from core.plugins.portable_identifiers import require_portable_plugin_identifier

__all__ = ("BackendUpdateChild",)


@dataclass(frozen=True, slots=True)
class BackendUpdateChild:
    plugin_name: str
    request_id: str
    backend_variant_id: str

    def __post_init__(self) -> None:
        require_portable_plugin_identifier(self.plugin_name, field_name="plugin_name")
        require_mutation_request_id(self.request_id)
        if require_backend_variant_id(self.backend_variant_id) != self.backend_variant_id:
            raise ValidationError("Backend update child variant must be canonical.")
