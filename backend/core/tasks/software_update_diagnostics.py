"""SoAI - Task-scoped software update diagnostics location and identity [backend/core/tasks/software_update_diagnostics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.files.path_policy import is_path_overlap_with_base
from core.files.windows_reparse_points import is_windows_reparse_point
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.atomic_writes import atomic_create_text_content_exclusive
from core.filesystem.open_files import read_regular_file_no_symlink
from core.meta.paths import join_data_abs
from core.platform.os import is_macos, is_windows
from core.runtime.instance_record import canonicalize_runtime_base_dir
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.tasks.identifiers import validate_optional_task_id
from core.tasks.software_update_versions import require_software_update_version
from core.validation.strict_integer import is_strict_int
from core.validation.strings import coerce_required_non_empty_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "MAX_DIAGNOSTICS_RECORD_BYTES",
    "UpdateDiagnosticsContext",
    "establish_update_diagnostics",
    "ensure_private_diagnostics_directory",
    "read_update_diagnostics_context",
    "read_update_diagnostics_locator",
    "read_transaction_diagnostics_locator",
    "require_private_diagnostics_directory",
    "resolve_update_diagnostics_state_base",
    "update_diagnostics_locator_path",
)

SCHEMA_VERSION = 1
CONTEXT_FILENAME = "update_diagnostics_context.json"
PROBE_FILENAME = "probe.json"
MAX_DIAGNOSTICS_RECORD_BYTES = 262144
DIAGNOSTICS_DIRECTORY_PARTS = ("SoAI", "update-diagnostics")
OWNER_ONLY_MODE = 0o700
GROUP_AND_OTHER_ACCESS_BITS = 0o077
INSTALLATION_DIRECTORY_HEX_LENGTH = 16
CONTEXT_FIELDS = frozenset(
    {
        "schema_version",
        "task_id",
        "transaction",
        "installation",
        "location",
        "from_version",
        "to_version",
    }
)


@dataclass(frozen=True, slots=True)
class UpdateDiagnosticsContext:
    task_id: str
    transaction: str
    installation: str
    location: str
    from_version: str
    to_version: str

    def to_mapping(self) -> JSONDict:
        return {
            "schema_version": SCHEMA_VERSION,
            "task_id": self.task_id,
            "transaction": self.transaction,
            "installation": self.installation,
            "location": self.location,
            "from_version": self.from_version,
            "to_version": self.to_version,
        }


def update_diagnostics_locator_path(base_path: str, task_id: str) -> str:
    validated_task_id = validate_optional_task_id(task_id)
    if validated_task_id is None or validated_task_id != task_id:
        raise StateError("Update diagnostics require a canonical task identity.")
    return join_data_abs(base_path, "state", f"software-update-{task_id}.diagnostics.json")


def resolve_update_diagnostics_state_base() -> str:
    if is_windows():
        state_base = os.environ.get("LOCALAPPDATA", "")
    elif is_macos():
        state_base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        state_base = os.environ.get("XDG_STATE_HOME", "") or os.path.join(
            os.path.expanduser("~"), ".local", "state"
        )
    if not os.path.isabs(state_base):
        raise StateError("The account-local state directory for update diagnostics is unavailable.")
    return os.path.normpath(state_base)


def require_private_diagnostics_directory(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    while parent != os.path.dirname(parent):
        parent_metadata = os.lstat(parent)
        if not stat.S_ISDIR(parent_metadata.st_mode) or is_windows_reparse_point(parent_metadata):
            raise StateError("Update diagnostics storage parents must be regular directories.")
        parent = os.path.dirname(parent)
    metadata = os.lstat(path)
    if not stat.S_ISDIR(metadata.st_mode) or is_windows_reparse_point(metadata):
        raise StateError("Update diagnostics storage must be a regular directory.")
    if os.name == "posix" and (
        metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) & GROUP_AND_OTHER_ACCESS_BITS
    ):
        raise StateError("Update diagnostics storage must be private to the executing account.")


def ensure_private_diagnostics_directory(
    path: str, *, directory_mode: int = OWNER_ONLY_MODE
) -> None:
    try:
        os.mkdir(path, directory_mode)
    except FileExistsError:
        require_private_diagnostics_directory(path)
        return
    require_private_diagnostics_directory(path)
    fsync_directory(os.path.dirname(path), strict=True)


def _parse_context(raw: bytes, *, field: str) -> UpdateDiagnosticsContext:
    payload = parse_json_dict(raw, field=field, reject_duplicate_keys=True)
    schema_version = payload.get("schema_version")
    if (
        frozenset(payload) != CONTEXT_FIELDS
        or not is_strict_int(schema_version)
        or schema_version != SCHEMA_VERSION
    ):
        raise StateError("Update diagnostics context does not match its contract.")
    task_id = validate_optional_task_id(payload.get("task_id"), field_name=f"{field} task_id")
    transaction = coerce_required_non_empty_str(payload.get("transaction"), label=field)
    location = coerce_required_non_empty_str(payload.get("location"), label=field)
    if (
        task_id is None
        or transaction != os.path.basename(transaction)
        or not os.path.isabs(location)
        or os.path.normpath(location) != location
    ):
        raise StateError("Update diagnostics context identity is invalid.")
    return UpdateDiagnosticsContext(
        task_id=task_id,
        transaction=transaction,
        installation=coerce_required_non_empty_str(payload.get("installation"), label=field),
        location=location,
        from_version=require_software_update_version(
            payload.get("from_version"), field=f"{field} from_version"
        ),
        to_version=require_software_update_version(
            payload.get("to_version"), field=f"{field} to_version"
        ),
    )


def _read_context_file(path: str, *, field: str) -> UpdateDiagnosticsContext:
    return _parse_context(
        read_regular_file_no_symlink(path, max_bytes=MAX_DIAGNOSTICS_RECORD_BYTES), field=field
    )


def _create_context_file(path: str, context: UpdateDiagnosticsContext, *, field: str) -> None:
    try:
        atomic_create_text_content_exclusive(
            path,
            serialize_json_compact_stable_strict(context.to_mapping()),
            file_mode=0o600,
            fsync_parent_directory=True,
        )
    except FileExistsError as exception:
        if _read_context_file(path, field=field) != context:
            raise StateError(
                "Update diagnostics context conflicts with the accepted operation."
            ) from exception


def read_update_diagnostics_locator(
    base_path: str, task_id: str
) -> UpdateDiagnosticsContext | None:
    locator_path = update_diagnostics_locator_path(base_path, task_id)
    if not os.path.lexists(locator_path):
        return None
    context = _read_context_file(locator_path, field="update diagnostics locator")
    if context.task_id != task_id or context.installation != canonicalize_runtime_base_dir(
        base_path
    ):
        raise StateError("Update diagnostics locator belongs to another operation.")
    installation_directory = hashlib.sha256(context.installation.encode("utf-8")).hexdigest()[
        :INSTALLATION_DIRECTORY_HEX_LENGTH
    ]
    location = os.path.normpath(context.location)
    for component in reversed((*DIAGNOSTICS_DIRECTORY_PARTS, installation_directory, task_id)):
        if os.path.basename(location) != component:
            raise StateError("Update diagnostics location does not match its operation.")
        location = os.path.dirname(location)
    return context


def read_update_diagnostics_context(
    *, base_path: str, transaction_path: str, transaction_name: str
) -> UpdateDiagnosticsContext | None:
    context_path = os.path.join(transaction_path, CONTEXT_FILENAME)
    if not os.path.lexists(context_path):
        return None
    context = _read_context_file(context_path, field="update diagnostics context")
    if (
        context.transaction != transaction_name
        or read_update_diagnostics_locator(base_path, context.task_id) != context
    ):
        raise StateError("Update diagnostics locator does not match its transaction.")
    return context


def establish_update_diagnostics(
    *,
    base_path: str,
    transaction_path: str,
    task_id: str,
    from_version: str,
    to_version: str,
    protected_trees: tuple[str, ...],
) -> UpdateDiagnosticsContext:
    update_diagnostics_locator_path(base_path, task_id)
    installation = canonicalize_runtime_base_dir(base_path)
    state_base = resolve_update_diagnostics_state_base()
    os.makedirs(state_base, mode=OWNER_ONLY_MODE, exist_ok=True)
    installation_directory = hashlib.sha256(installation.encode("utf-8")).hexdigest()[
        :INSTALLATION_DIRECTORY_HEX_LENGTH
    ]
    location = state_base
    for part in (*DIAGNOSTICS_DIRECTORY_PARTS, installation_directory, task_id):
        location = os.path.join(location, part)
        if any(
            is_path_overlap_with_base(tree, location)
            for tree in (base_path, transaction_path, *protected_trees)
        ):
            raise StateError("Update diagnostics storage overlaps the installation or its state.")
        directory_mode = (
            0o777 if is_windows() and part == DIAGNOSTICS_DIRECTORY_PARTS[0] else OWNER_ONLY_MODE
        )
        ensure_private_diagnostics_directory(location, directory_mode=directory_mode)
    context = UpdateDiagnosticsContext(
        task_id=task_id,
        transaction=os.path.basename(transaction_path),
        installation=installation,
        location=location,
        from_version=from_version,
        to_version=to_version,
    )
    probe = {"task_id": task_id, "transaction": context.transaction}
    probe_path = os.path.join(location, PROBE_FILENAME)
    atomic_create_text_content_exclusive(
        probe_path,
        serialize_json_compact_stable_strict(probe),
        ensure_parent=False,
        file_mode=0o600,
        fsync_parent_directory=True,
    )
    probe_readback = parse_json_dict(
        read_regular_file_no_symlink(probe_path, max_bytes=MAX_DIAGNOSTICS_RECORD_BYTES)
    )
    if probe_readback != probe:
        raise StateError("Update diagnostics storage could not read back its probe.")
    os.remove(probe_path)
    fsync_directory(location, strict=True)
    _create_context_file(
        update_diagnostics_locator_path(base_path, task_id),
        context,
        field="update diagnostics locator",
    )
    _create_context_file(
        os.path.join(transaction_path, CONTEXT_FILENAME),
        context,
        field="update diagnostics context",
    )
    return context


def read_transaction_diagnostics_locator(
    base_path: str, transaction_name: str
) -> UpdateDiagnosticsContext | None:
    state_path = join_data_abs(base_path, "state")
    if not os.path.isdir(state_path):
        return None
    matching_context: UpdateDiagnosticsContext | None = None
    for name in os.listdir(state_path):
        if not name.startswith("software-update-") or not name.endswith(".diagnostics.json"):
            continue
        task_id = name.removeprefix("software-update-").removesuffix(".diagnostics.json")
        context = read_update_diagnostics_locator(base_path, task_id)
        if context is None or context.transaction != transaction_name:
            continue
        if matching_context is not None:
            raise StateError("Multiple update diagnostics locators claim the same transaction.")
        matching_context = context
    return matching_context
