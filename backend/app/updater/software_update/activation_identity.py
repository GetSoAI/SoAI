"""SoAI - Accepted update activation identity validation [backend/app/updater/software_update/activation_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from app.updater.software_update.install_transaction_state import UpdateTransactionPaths
from core.errors.exceptions import StateError
from core.licensing.edition import require_licensing_edition
from core.meta.versioning import parse_semantic_version
from core.tasks.identifiers import validate_optional_task_id
from core.types.json import JSONDict
from core.validation.strings import coerce_required_non_empty_str

__all__ = ("UpdateActivationIdentity", "parse_update_activation_identity")


@dataclass(frozen=True, slots=True)
class UpdateActivationIdentity:
    paths: UpdateTransactionPaths
    task_id: str
    edition: str
    from_version: str
    to_version: str
    config_path: str

    def to_mapping(self) -> JSONDict:
        return {
            "task_id": self.task_id,
            "edition": self.edition,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "config_path": self.config_path,
        }


def parse_update_activation_identity(
    paths: UpdateTransactionPaths, payload: JSONDict
) -> UpdateActivationIdentity:
    if set(payload) != {"task_id", "edition", "from_version", "to_version", "config_path"}:
        raise StateError("Update activation identity fields are invalid.")
    task_id = validate_optional_task_id(payload.get("task_id"))
    if task_id is None or task_id != payload.get("task_id"):
        raise StateError("Update activation task identity is not canonical.")
    edition = require_licensing_edition(
        coerce_required_non_empty_str(payload.get("edition"), label="activation edition")
    )
    from_version = coerce_required_non_empty_str(
        payload.get("from_version"), label="activation baseline"
    )
    to_version = coerce_required_non_empty_str(payload.get("to_version"), label="activation target")
    parse_semantic_version(from_version)
    parse_semantic_version(to_version)
    config_path = coerce_required_non_empty_str(
        payload.get("config_path"), label="activation configuration"
    )
    if config_path != os.path.abspath(config_path):
        raise StateError("Update activation configuration path must be absolute.")
    return UpdateActivationIdentity(paths, task_id, edition, from_version, to_version, config_path)
