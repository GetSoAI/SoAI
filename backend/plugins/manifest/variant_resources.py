"""SoAI - Nonexecuting plugin variant resource extraction [backend/plugins/manifest/variant_resources.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
import hashlib
import zipfile
from collections.abc import Sequence

from core.archives.zip_plan import ValidatedZipPlan
from core.errors.exceptions import ValidationError
from core.plugins.backend_variant_resources import (
    MAX_BACKEND_VARIANT_RESOURCE_BYTES,
    parse_backend_variant_resource,
    require_backend_variant_resource_name,
)
from core.types.json import JSONDict
from plugins.manifest.ast_contracts import extract_class_assignments, get_plugin_class_node
from plugins.manifest.class_field_contract import PLUGIN_FIELD_BACKEND_VARIANT_OPTIONS
from plugins.package_content import PluginPackageMemberDigest

__all__ = ("read_static_backend_variant_resource",)


def read_static_backend_variant_resource(
    tree: ast.Module,
    archive: zipfile.ZipFile,
    plan: ValidatedZipPlan,
    digests: Sequence[PluginPackageMemberDigest],
) -> list[JSONDict] | None:
    classes = [
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Plugin"
    ]
    if len(classes) != 1:
        return None
    expression = extract_class_assignments(get_plugin_class_node(tree)).get(
        PLUGIN_FIELD_BACKEND_VARIANT_OPTIONS
    )
    if not isinstance(expression, ast.Call):
        return None
    message = (
        "Backend variant metadata requires a literal or an explicit static SDK resource reference."
    )
    if (
        not isinstance(expression.func, ast.Attribute)
        or not isinstance(expression.func.value, ast.Name)
        or expression.func.value.id != "plugin_sdk"
        or expression.func.attr != "load_backend_variant_options"
    ):
        raise ValidationError(message)
    if expression.keywords or len(expression.args) != 2:
        raise ValidationError(message)
    source_file, resource_name = expression.args
    if (
        not isinstance(source_file, ast.Name)
        or source_file.id != "__file__"
        or not isinstance(resource_name, ast.Constant)
        or not isinstance(resource_name.value, str)
    ):
        raise ValidationError(message)
    name = require_backend_variant_resource_name(resource_name.value)
    member = next((member for member in plan.members if member.archive_path == name), None)
    if (
        member is None
        or member.is_directory
        or member.file_size > MAX_BACKEND_VARIANT_RESOURCE_BYTES
    ):
        raise ValidationError(
            "Backend variant metadata resource is missing, invalid or exceeds 1 MiB."
        )
    with archive.open(member.zip_info) as source:
        content = source.read(MAX_BACKEND_VARIANT_RESOURCE_BYTES + 1)
    digest = next((digest for digest in digests if digest.logical_path == name), None)
    if (
        digest is None
        or len(content) != digest.file_size
        or hashlib.sha256(content).hexdigest() != digest.sha256_hex
    ):
        raise ValidationError("Backend variant metadata changed during package inspection.")
    return parse_backend_variant_resource(content)
