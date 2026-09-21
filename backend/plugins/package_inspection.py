"""SoAI - Plugin ZIP package snapshot inspection [backend/plugins/package_inspection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
import hashlib
import io
import zipfile
import zlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.archives.constants import CHUNK_READ_SIZE
from core.archives.zip_plan import ValidatedZipMember, ValidatedZipPlan
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.files.content_hashing import hash_seekable_binary_stream_content
from core.models.parameter_schema_document import validate_parameter_schema_document
from core.plugins.logo_contract import (
    LOGO_FILENAMES,
    MAX_LOGO_SOURCE_BYTES,
    PluginLogoSource,
)
from core.serialization.json_parsing import MAX_JSON_NESTING_DEPTH, parse_json_value
from core.types.json import is_json_dict
from plugins.package_archive import open_validated_plugin_package
from plugins.package_content import (
    PluginPackageContent,
    PluginPackageMemberDigest,
    PluginPythonMemberAudit,
)
from plugins.package_paths import COMPLETION_RECORD_NAME

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "PluginPackageSnapshot",
    "inspect_plugin_package_stream",
)

MAX_PLUGIN_PYTHON_FILES = 512
MAX_PLUGIN_PYTHON_MEMBER_BYTES = 8 * 1024 * 1024
MAX_PLUGIN_PYTHON_TOTAL_BYTES = 64 * 1024 * 1024
MAX_MODEL_PARAMETER_SCHEMA_BYTES = 8 * MIB_BYTES
MODEL_PARAMETER_SCHEMA_RESOURCE = "model_parameters.json"
PLUGIN_ENTRYPOINT = "__init__.py"


@dataclass(frozen=True, slots=True)
class PluginPackageSnapshot:
    content: PluginPackageContent
    parameter_schema: JSONDict | None
    logo_source: PluginLogoSource


def _parse_python_member(
    plugin_name: str,
    member: ValidatedZipMember,
    source_bytes: bytes,
) -> PluginPythonMemberAudit:
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exception:
        raise ValidationError(
            f"Plugin package Python member is not valid UTF-8: {member.archive_path}",
        ) from exception
    logical_path = member.archive_path
    try:
        parsed_source = ast.parse(source_text, filename=logical_path)
    except SyntaxError as exception:
        raise ValidationError(
            f"Plugin package Python member for '{plugin_name}' is not valid Python: {logical_path}",
        ) from exception
    return PluginPythonMemberAudit(
        logical_path=logical_path,
        source_text=source_text,
        parsed_source=parsed_source,
        file_size=member.file_size,
    )


def _python_plan_members(plan: ValidatedZipPlan) -> list[ValidatedZipMember]:
    if not plan.members:
        raise ValidationError("Plugin package ZIP archive must not be empty.")
    entrypoints = [
        member
        for member in plan.members
        if member.archive_path.casefold() == PLUGIN_ENTRYPOINT.casefold()
    ]
    if len(entrypoints) != 1:
        raise ValidationError("Plugin package must contain exactly one root __init__.py.")
    entrypoint = entrypoints[0]
    if entrypoint.archive_path != PLUGIN_ENTRYPOINT or entrypoint.is_directory:
        raise ValidationError("Plugin package requires a regular root __init__.py entrypoint.")
    python_members: list[ValidatedZipMember] = []
    python_total_size = 0
    for member in plan.members:
        if member.archive_path == COMPLETION_RECORD_NAME:
            raise ValidationError(
                f"Plugin package contains reserved member: {COMPLETION_RECORD_NAME}",
            )
        components = member.archive_path.split("/")
        lower_components = [component.casefold() for component in components]
        lower_path = member.archive_path.casefold()
        if lower_path.endswith((".pyc", ".pyo")) or "__pycache__" in lower_components:
            raise ValidationError(
                f"Plugin package contains forbidden bytecode artifact: {member.archive_path}",
            )
        if member.is_directory or not lower_path.endswith(".py"):
            continue
        if member.file_size > MAX_PLUGIN_PYTHON_MEMBER_BYTES:
            raise ValidationError(
                f"Plugin package Python member exceeds 8 MiB: {member.archive_path}",
            )
        python_total_size += member.file_size
        if python_total_size > MAX_PLUGIN_PYTHON_TOTAL_BYTES:
            raise ValidationError("Plugin package Python source exceeds 64 MiB in aggregate.")
        python_members.append(member)
    if len(python_members) > MAX_PLUGIN_PYTHON_FILES:
        raise ValidationError("Plugin package exceeds the limit of 512 Python files.")
    return python_members


def _parameter_schema_plan_member(
    plan: ValidatedZipPlan,
) -> ValidatedZipMember | None:
    for member in plan.members:
        if member.archive_path != MODEL_PARAMETER_SCHEMA_RESOURCE:
            continue
        if member.is_directory:
            raise ValidationError(
                f"Plugin package {MODEL_PARAMETER_SCHEMA_RESOURCE} must be a regular file.",
            )
        if member.file_size > MAX_MODEL_PARAMETER_SCHEMA_BYTES:
            raise ValidationError(
                f"Plugin package {MODEL_PARAMETER_SCHEMA_RESOURCE} exceeds 8 MiB.",
            )
        return member
    return None


def _inspect_member_contents(
    zip_file: zipfile.ZipFile,
    plan: ValidatedZipPlan,
    python_plan_members: list[ValidatedZipMember],
    parameter_schema_member: ValidatedZipMember | None,
) -> tuple[tuple[PluginPackageMemberDigest, ...], dict[str, bytes], bytes | None, PluginLogoSource]:
    python_paths = {member.archive_path for member in python_plan_members}
    python_source_buffers = {member.archive_path: bytearray() for member in python_plan_members}
    parameter_schema_buffer = bytearray() if parameter_schema_member is not None else None
    member_digests: list[PluginPackageMemberDigest] = []
    logo_members = [
        member
        for member in plan.members
        if "/" not in member.archive_path.rstrip("/")
        and member.archive_path.casefold().startswith("logo.")
    ]
    logo_member = logo_members[0] if len(logo_members) == 1 else None
    logo_source = PluginLogoSource()
    if logo_members:
        if logo_member is None:
            logo_source = PluginLogoSource(
                rejection="Archive contains multiple root artwork candidates."
            )
        elif logo_member.is_directory or logo_member.archive_path not in LOGO_FILENAMES:
            logo_source = PluginLogoSource(
                rejection="Artwork must be a regular root logo.png or logo.webp."
            )
        elif not 1 <= logo_member.file_size <= MAX_LOGO_SOURCE_BYTES:
            logo_source = PluginLogoSource(
                rejection="Artwork source must contain between 1 and 1048576 bytes."
            )
        else:
            logo_source = PluginLogoSource(filename=logo_member.archive_path)
    logo_buffer = bytearray()
    for member in plan.members:
        if member.is_directory:
            continue
        digest = hashlib.sha256()
        total_bytes = 0
        with zip_file.open(member.zip_info) as source_stream:
            while True:
                chunk = source_stream.read(CHUNK_READ_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
                total_bytes += len(chunk)
                if member is logo_member and logo_source.filename is not None:
                    if total_bytes <= MAX_LOGO_SOURCE_BYTES:
                        logo_buffer.extend(chunk)
                    else:
                        logo_buffer.clear()
                        logo_source = PluginLogoSource(
                            rejection="Artwork exceeds the source byte limit."
                        )
                if member.archive_path in python_paths:
                    python_source_buffers[member.archive_path].extend(chunk)
                if parameter_schema_member is not None and member is parameter_schema_member:
                    if total_bytes > MAX_MODEL_PARAMETER_SCHEMA_BYTES:
                        raise ValidationError(
                            f"Plugin package {MODEL_PARAMETER_SCHEMA_RESOURCE} exceeds 8 MiB.",
                        )
                    if parameter_schema_buffer is None:
                        raise ValidationError("Parameter schema buffer was not initialized.")
                    parameter_schema_buffer.extend(chunk)
        if total_bytes != member.file_size:
            raise ValidationError(
                f"Plugin package member size does not match its ZIP metadata: {member.archive_path}",
            )
        member_digests.append(
            PluginPackageMemberDigest(
                logical_path=member.archive_path,
                destination_path=member.destination_path,
                file_size=member.file_size,
                sha256_hex=digest.hexdigest(),
            )
        )
    return (
        tuple(member_digests),
        {path: bytes(source_buffer) for path, source_buffer in python_source_buffers.items()},
        bytes(parameter_schema_buffer) if parameter_schema_buffer is not None else None,
        PluginLogoSource(logo_source.filename, bytes(logo_buffer), logo_source.rejection),
    )


def _parse_parameter_schema(
    plugin_name: str,
    resource_bytes: bytes | None,
) -> JSONDict | None:
    if resource_bytes is None:
        return None
    parsed = parse_json_value(
        resource_bytes,
        field=f"Plugin '{plugin_name}' {MODEL_PARAMETER_SCHEMA_RESOURCE}",
        max_depth=MAX_JSON_NESTING_DEPTH,
        strict_utf8=True,
        reject_duplicate_keys=True,
    )
    if not is_json_dict(parsed):
        raise ValidationError(
            f"Plugin '{plugin_name}' {MODEL_PARAMETER_SCHEMA_RESOURCE} must be a JSON object.",
        )
    validate_parameter_schema_document(
        plugin_name,
        parsed,
        require_categories=True,
    )
    return parsed


def inspect_plugin_package_stream(
    plugin_name: str,
    file_handle: io.BufferedIOBase | io.RawIOBase,
) -> PluginPackageSnapshot:
    archive_hash = hash_seekable_binary_stream_content(file_handle).sha256_hex
    try:
        with open_validated_plugin_package(file_handle) as (zip_file, plan):
            python_plan_members = _python_plan_members(plan)
            parameter_schema_member = _parameter_schema_plan_member(plan)
            member_digests, python_sources, parameter_schema_bytes, logo_source = (
                _inspect_member_contents(
                    zip_file,
                    plan,
                    python_plan_members,
                    parameter_schema_member,
                )
            )
            python_members = tuple(
                _parse_python_member(
                    plugin_name,
                    member,
                    python_sources[member.archive_path],
                )
                for member in python_plan_members
            )
            parameter_schema = _parse_parameter_schema(plugin_name, parameter_schema_bytes)
    except (EOFError, OSError, zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error) as exception:
        raise ValidationError(
            f"Plugin package for '{plugin_name}' must be a valid ZIP archive.",
        ) from exception
    except RuntimeError as exception:
        raise ValidationError(
            f"Plugin package for '{plugin_name}' contains an unreadable ZIP member.",
        ) from exception
    entrypoint = next(
        member for member in python_members if member.logical_path == PLUGIN_ENTRYPOINT
    )
    return PluginPackageSnapshot(
        content=PluginPackageContent(
            archive_hash=archive_hash,
            zip_plan=plan,
            expanded_size=plan.total_uncompressed_size,
            member_digests=member_digests,
            entrypoint=entrypoint,
            python_members=python_members,
        ),
        parameter_schema=parameter_schema,
        logo_source=logo_source,
    )
