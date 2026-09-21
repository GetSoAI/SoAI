"""SoAI - Plugin manifest AST extraction without execution [backend/plugins/manifest/ast_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json import is_json_dict, is_str_list
from plugins.manifest.ast_contracts import (
    MANIFEST_CLASS_NAME,
    eval_external_provider_mode,
    eval_openai_flags,
    eval_required_bool,
    eval_required_literal,
    extract_class_assignments,
    get_plugin_class_node,
)
from plugins.manifest.class_field_contract import (
    PLUGIN_FIELD_ALIASES,
    PLUGIN_FIELD_AUTHOR_SOAIPLUGIN,
    PLUGIN_FIELD_BACKEND_VARIANT_OPTIONS,
    PLUGIN_FIELD_DEFAULT_CONFIGURATION,
    PLUGIN_FIELD_DESCRIPTION_SOAIPLUGIN,
    PLUGIN_FIELD_EXTERNAL_PROVIDER_DEFAULTS,
    PLUGIN_FIELD_LICENSE_MANAGED_BACKEND,
    PLUGIN_FIELD_LICENSE_SOAIPLUGIN,
    PLUGIN_FIELD_LOCAL_MODELS,
    PLUGIN_FIELD_LOCAL_RESOURCES,
    PLUGIN_FIELD_MAX_CONCURRENT_REQUESTS,
    PLUGIN_FIELD_MODEL_REPOSITORY,
    PLUGIN_FIELD_MODEL_TYPES,
    PLUGIN_FIELD_NAME,
    PLUGIN_FIELD_PACKAGE_DEPENDENCIES,
    PLUGIN_FIELD_PERSISTENT,
    PLUGIN_FIELD_PLUGIN_DEPENDENCIES,
    PLUGIN_FIELD_REQUIRED_SOAI_VERSION,
    PLUGIN_FIELD_REQUIRED_SYSTEM_CAPABILITIES,
    PLUGIN_FIELD_SUPPORTED_MODALITIES,
    PLUGIN_FIELD_SUPPORTS_BACKEND_INSTALLATION,
    PLUGIN_FIELD_SUPPORTS_BACKEND_PROCESS_TRACKING,
    PLUGIN_FIELD_SUPPORTS_CLONING,
    PLUGIN_FIELD_SUPPORTS_CONFIGURATION,
    PLUGIN_FIELD_SUPPORTS_EXTERNAL_PROVIDERS,
    PLUGIN_FIELD_SUPPORTS_GPU_BINDING,
    PLUGIN_FIELD_SUPPORTS_MODEL_DELETION,
    PLUGIN_FIELD_SUPPORTS_MODEL_DOWNLOAD,
    PLUGIN_FIELD_SUPPORTS_MODEL_SEARCH,
    PLUGIN_FIELD_SUPPORTS_MODEL_VARIANT_DISCOVERY,
    PLUGIN_FIELD_SUPPORTS_PROMPT_TOKEN_COUNTING,
    PLUGIN_FIELD_VERSION_SOAIPLUGIN,
    PLUGIN_FIELD_WEBSITE_BACKEND,
    PLUGIN_FIELD_WEBSITE_SOAIPLUGIN,
)
from plugins.manifest.payloads import (
    PluginManifestPayloadSource,
    build_plugin_manifest_payload,
)
from plugins.package_dependency_validation import ensure_declared_package_dependencies
from plugins.security import ensure_import_tree_has_no_forbidden_imports

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from plugins.package_audit import PluginPackageAudit
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("extract_plugin_manifest_from_disk",)


def _extract_declared_package_names(manifest_payload: JSONDict) -> list[str]:
    dependencies_value = manifest_payload.get("dependencies")
    if not is_json_dict(dependencies_value):
        raise ValidationError("Internal error: plugin dependency payload is not a JSON object.")
    packages_value = dependencies_value.get("packages")
    if not is_str_list(packages_value):
        raise ValidationError("Internal error: plugin package dependency payload is invalid.")
    return list(packages_value)


def extract_plugin_manifest_from_disk(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    enforce_safety_validation: bool = True,
    package_audit: PluginPackageAudit,
) -> JSONDict:
    del manager
    tree = package_audit.content.entrypoint.parsed_source
    if enforce_safety_validation and not package_audit.imports_validated:
        for python_member in package_audit.content.python_members:
            ensure_import_tree_has_no_forbidden_imports(plugin_name, python_member.parsed_source)
    class_node = get_plugin_class_node(tree)
    assignments = extract_class_assignments(class_node)
    plugin_deps = eval_required_literal(assignments, PLUGIN_FIELD_PLUGIN_DEPENDENCIES)
    package_deps = eval_required_literal(assignments, PLUGIN_FIELD_PACKAGE_DEPENDENCIES)
    manifest_payload = build_plugin_manifest_payload(
        PluginManifestPayloadSource(
            plugin_name=plugin_name,
            name=eval_required_literal(assignments, PLUGIN_FIELD_NAME),
            version_soaiplugin=eval_required_literal(
                assignments,
                PLUGIN_FIELD_VERSION_SOAIPLUGIN,
            ),
            author_soaiplugin=eval_required_literal(
                assignments,
                PLUGIN_FIELD_AUTHOR_SOAIPLUGIN,
            ),
            description_soaiplugin=eval_required_literal(
                assignments,
                PLUGIN_FIELD_DESCRIPTION_SOAIPLUGIN,
            ),
            website_soaiplugin=eval_required_literal(
                assignments,
                PLUGIN_FIELD_WEBSITE_SOAIPLUGIN,
            ),
            license_soaiplugin=eval_required_literal(assignments, PLUGIN_FIELD_LICENSE_SOAIPLUGIN),
            website_backend=eval_required_literal(assignments, PLUGIN_FIELD_WEBSITE_BACKEND),
            license_managed_backend=(
                eval_required_literal(assignments, PLUGIN_FIELD_LICENSE_MANAGED_BACKEND)
                if PLUGIN_FIELD_LICENSE_MANAGED_BACKEND in assignments
                else None
            ),
            model_repository=eval_required_literal(assignments, PLUGIN_FIELD_MODEL_REPOSITORY),
            model_types=eval_required_literal(assignments, PLUGIN_FIELD_MODEL_TYPES),
            required_soai_version=eval_required_literal(
                assignments,
                PLUGIN_FIELD_REQUIRED_SOAI_VERSION,
            ),
            aliases=eval_required_literal(assignments, PLUGIN_FIELD_ALIASES),
            plugin_dependencies=plugin_deps,
            package_dependencies=package_deps,
            supported_modalities=eval_required_literal(
                assignments,
                PLUGIN_FIELD_SUPPORTED_MODALITIES,
            ),
            local_resources=eval_required_bool(assignments, PLUGIN_FIELD_LOCAL_RESOURCES),
            local_models=eval_required_bool(assignments, PLUGIN_FIELD_LOCAL_MODELS),
            persistent=eval_required_bool(assignments, PLUGIN_FIELD_PERSISTENT),
            max_concurrent_requests=eval_required_literal(
                assignments,
                PLUGIN_FIELD_MAX_CONCURRENT_REQUESTS,
            ),
            supports_backend_installation=eval_required_bool(
                assignments,
                PLUGIN_FIELD_SUPPORTS_BACKEND_INSTALLATION,
            ),
            supports_backend_process_tracking=eval_required_bool(
                assignments,
                PLUGIN_FIELD_SUPPORTS_BACKEND_PROCESS_TRACKING,
            ),
            supports_model_deletion=eval_required_bool(
                assignments,
                PLUGIN_FIELD_SUPPORTS_MODEL_DELETION,
            ),
            supports_model_download=eval_required_bool(
                assignments,
                PLUGIN_FIELD_SUPPORTS_MODEL_DOWNLOAD,
            ),
            supports_configuration=eval_required_bool(
                assignments,
                PLUGIN_FIELD_SUPPORTS_CONFIGURATION,
            ),
            supports_gpu_binding=(
                eval_required_bool(assignments, PLUGIN_FIELD_SUPPORTS_GPU_BINDING)
                if PLUGIN_FIELD_SUPPORTS_GPU_BINDING in assignments
                else False
            ),
            supports_external_providers=eval_required_bool(
                assignments,
                PLUGIN_FIELD_SUPPORTS_EXTERNAL_PROVIDERS,
            ),
            external_provider_mode=eval_external_provider_mode(assignments),
            supports_cloning=eval_required_bool(assignments, PLUGIN_FIELD_SUPPORTS_CLONING),
            required_system_capabilities=eval_required_literal(
                assignments,
                PLUGIN_FIELD_REQUIRED_SYSTEM_CAPABILITIES,
            ),
            openai_flag_values=eval_openai_flags(assignments),
            class_name=MANIFEST_CLASS_NAME,
            external_provider_defaults=(
                eval_required_literal(assignments, PLUGIN_FIELD_EXTERNAL_PROVIDER_DEFAULTS)
                if PLUGIN_FIELD_EXTERNAL_PROVIDER_DEFAULTS in assignments
                else None
            ),
            default_configuration=(
                eval_required_literal(assignments, PLUGIN_FIELD_DEFAULT_CONFIGURATION)
                if PLUGIN_FIELD_DEFAULT_CONFIGURATION in assignments
                else {}
            ),
            parameter_schema=package_audit.parameter_schema,
            backend_variant_options=(
                eval_required_literal(assignments, PLUGIN_FIELD_BACKEND_VARIANT_OPTIONS)
                if PLUGIN_FIELD_BACKEND_VARIANT_OPTIONS in assignments
                else []
            ),
            supports_model_search=(
                eval_required_bool(assignments, PLUGIN_FIELD_SUPPORTS_MODEL_SEARCH)
                if PLUGIN_FIELD_SUPPORTS_MODEL_SEARCH in assignments
                else False
            ),
            supports_model_variant_discovery=(
                eval_required_bool(assignments, PLUGIN_FIELD_SUPPORTS_MODEL_VARIANT_DISCOVERY)
                if PLUGIN_FIELD_SUPPORTS_MODEL_VARIANT_DISCOVERY in assignments
                else False
            ),
            supports_prompt_token_counting=(
                eval_required_bool(assignments, PLUGIN_FIELD_SUPPORTS_PROMPT_TOKEN_COUNTING)
                if PLUGIN_FIELD_SUPPORTS_PROMPT_TOKEN_COUNTING in assignments
                else False
            ),
        ),
    )
    package_names = _extract_declared_package_names(manifest_payload)
    dependency_trees = tuple(
        member.parsed_source for member in package_audit.content.python_members
    )
    for dependency_tree in dependency_trees:
        ensure_declared_package_dependencies(plugin_name, dependency_tree, package_names)
    return manifest_payload
