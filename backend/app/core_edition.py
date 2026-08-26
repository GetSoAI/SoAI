"""SoAI - Core edition composition [backend/app/core_edition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.edition_composition import (
    EditionCapabilities,
    EditionComposition,
    HostManagementServiceComposition,
    LifecycleComposition,
    TaskComposition,
    UpdaterComposition,
)
from app.updater.software_update.edition_preflight import validate_core_staged_update
from core.licensing.policy import EditionLicensingPolicy
from core.meta.version import __version__
from core.mutations.edition_composition import DurableMutationComposition
from core.mutations.storage_composition import MutationStorageComposition
from core.tasks.command_routes import build_base_task_command_routes
from core.tasks.type_catalog import build_base_task_catalog
from features.api.runtime.container.route_composition import ApiRouteComposition

__all__ = ("build_core_edition_composition",)


def build_core_edition_composition() -> EditionComposition:
    return EditionComposition(
        capabilities=EditionCapabilities(
            edition="soai-core",
            webui_relative_path="frontend",
            webui_fallback_relative_paths=(),
            host_management_available=False,
            host_management_enabled=False,
        ),
        licensing=EditionLicensingPolicy(
            edition="soai-core",
            legal_catalog_relative_paths=("licenses/legal_document_catalog.json",),
            legal_document_ids=frozenset(
                (
                    "commercial_support_terms",
                    "organization_evaluation_terms",
                    "soai_core_change_dates",
                    "soai_core_license",
                    "standard_commercial_license",
                )
            ),
            controlling_license_relative_path="LICENSE.md",
            controlling_license_name="SoAI Source-Available License 1.0",
            evaluation_terms_relative_path="ORGANIZATION-EVALUATION-TERMS.md",
            evaluation_terms_name="SoAI Organization Evaluation Terms",
            personal_purchase_terms_relative_path=None,
            personal_purchase_terms_name=None,
            licensed_product_scope="soai_core",
            organizational_evaluation_permitted=True,
            purchase_url="https://soai.to/licensing",
            contact_url="https://soai.to/contact",
        ),
        host_management=HostManagementServiceComposition(build_services=None),
        api_routes=ApiRouteComposition(
            host_management_router_factory=None,
            registrars=(),
        ),
        tasks=TaskComposition(
            catalog=build_base_task_catalog(),
            command_routes=build_base_task_command_routes(),
        ),
        durable_mutations=DurableMutationComposition(
            operation_matches=None,
            decode_command=None,
            claim_expired=None,
            command_is_recovery=None,
            command_requested_recovery=None,
            storage=MutationStorageComposition(
                admission_hook=None,
                recovery_release=None,
            ),
        ),
        lifecycle=LifecycleComposition(
            ensure_host_persistence=None,
            restart_cli_module="app.cli.entrypoint",
        ),
        updater=UpdaterComposition(
            edition="soai-core",
            product_version=str(__version__),
            core_version=str(__version__),
            entrypoint_relative_path="backend/main.py",
            cli_module="app.updater.cli",
            cli_relative_path="backend/app/updater/cli.py",
            post_update_hook_module="app.updater.post_update_hook",
            post_update_hook_relative_path="backend/app/updater/post_update_hook.py",
            validate_staged_payload=validate_core_staged_update,
        ),
    )
