"""SoAI - Plugin manifest compatibility checks [backend/plugins/state/manifest_compatibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from packaging.specifiers import InvalidSpecifier, SpecifierSet

from core.errors.exceptions import StateError
from core.errors.payload import ErrorPublicPayload
from core.hardware.protocols import GetGpuInfoCallable
from core.logging.trace import get_logger
from core.meta.versioning import parse_semantic_version
from core.runtime.platform import normalize_platform_id
from core.state.compatibility import CompatibilityInfo, IncompatibilityReason
from core.validation.boolean_coercion import coerce_bool_with_recovery
from plugins.state.capability_normalization import (
    as_json_list,
    format_capability_values,
    normalize_required_capabilities,
)
from plugins.state.compatibility import build_compatibility_info
from plugins.state.host_snapshot import get_host_capability_snapshot
from plugins.state.version_compatibility import determine_version_mitigation

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("check_plugin_manifest_compatibility",)

LOGGER_NAME = "SoAI.plugins.state.manifest_compatibility"


async def check_plugin_manifest_compatibility(
    plugin_name: str,
    manifest: JSONDict,
    core_version: str,
    get_gpu_info: GetGpuInfoCallable,
    existing_record: JSONDict | None = None,
) -> CompatibilityInfo:
    override_flag = coerce_bool_with_recovery(
        existing_record or {},
        "incompatibility_override",
        logger=get_logger(LOGGER_NAME),
        operation="plugins.state.manifest_compatibility.coerce_bool",
        default=False,
        recover_message="Failed to parse compatibility bool flag (non-critical).",
    )
    version_result = _check_manifest_version(plugin_name, manifest, core_version)
    if version_result is not None:
        return version_result
    return await _check_manifest_system_capabilities(
        plugin_name,
        manifest,
        get_gpu_info,
        override_flag,
    )


def _check_manifest_version(
    plugin_name: str,
    manifest: JSONDict,
    core_version: str,
) -> CompatibilityInfo | None:
    required_spec_value = manifest.get("core_compat")
    required_spec = required_spec_value if isinstance(required_spec_value, str) else ""
    if not required_spec.strip():
        raise StateError(
            f"Plugin '{plugin_name}' declares invalid REQUIRED_SOAI_VERSION '{required_spec}'.",
        )
    try:
        current_version_parsed = parse_semantic_version(core_version)
    except (TypeError, ValueError) as exception:
        raise StateError(
            f"SoAI core version '{core_version}' is not a valid semantic version: {exception}",
        ) from exception
    try:
        specifier = SpecifierSet(str(required_spec))
    except (InvalidSpecifier, TypeError) as exception:
        error_payload = ErrorPublicPayload(
            code="config_error",
            message=str(exception),
            details={"required_version": str(required_spec)},
        ).to_dict()
        error_details = (
            error_payload if isinstance(error_payload, dict) else {"error": str(error_payload)}
        )
        return build_compatibility_info(
            IncompatibilityReason.BROKEN_PLUGIN,
            f"Plugin '{plugin_name}' declares invalid REQUIRED_SOAI_VERSION '{required_spec}': {exception}",
            {
                "required_version": str(required_spec),
                "error": error_details,
            },
            False,
        )
    if specifier.contains(current_version_parsed, prereleases=True):
        return None
    action, target = determine_version_mitigation(specifier, current_version_parsed)
    message_base = f"Requires SoAI version {required_spec}. Current: {core_version}."
    message = (
        f"{message_base} Downgrade SoAI to version {target} if available to use this plugin."
        if action == "downgrade" and target
        else f"{message_base} Update SoAI to use this plugin."
    )
    details: JSONDict = {
        "required_version": str(required_spec),
        "detected_version": core_version,
    }
    if target:
        details["suggested_version"] = target
    return build_compatibility_info(
        IncompatibilityReason.VERSION_INCOMPATIBLE,
        message,
        details,
        False,
    )


async def _check_manifest_system_capabilities(
    _plugin_name: str,
    manifest: JSONDict,
    get_gpu_info: GetGpuInfoCallable,
    override_flag: bool,
) -> CompatibilityInfo:
    required_capabilities_value = manifest.get("required_system_capabilities")
    required_capabilities: JSONValue = (
        dict(required_capabilities_value)
        if isinstance(required_capabilities_value, Mapping)
        else {}
    )
    raw_caps, normalized_caps = normalize_required_capabilities(required_capabilities)
    normalized_gpu = normalized_caps.get("gpu")
    host_snapshot = await get_host_capability_snapshot(
        None,
        get_gpu_info,
        include_gpu_inventory=normalized_gpu is not None,
    )
    normalized_platforms = normalized_caps.get("platforms") or normalized_caps.get("platform")
    if normalized_platforms:
        detected_platform_value = str(host_snapshot.get("platform") or "").strip().lower()
        detected_platform = (
            normalize_platform_id(detected_platform_value) or detected_platform_value
        )
        if "any" not in normalized_platforms and detected_platform not in normalized_platforms:
            raw_platforms = raw_caps.get("platforms", []) or raw_caps.get("platform", [])
            required_text = format_capability_values(raw_platforms)
            detected_text = detected_platform.upper() or "UNKNOWN"
            return build_compatibility_info(
                IncompatibilityReason.OS_INCOMPATIBLE,
                f"Requires {required_text}. Detected: {detected_text}. Override at your own risk.",
                {
                    "required_platforms": as_json_list(raw_platforms),
                    "detected_platform": detected_platform or None,
                },
                override_flag,
            )
    if normalized_os := normalized_caps.get("os"):
        detected_os = str(host_snapshot.get("os") or "").strip().lower()
        if "any" not in normalized_os and detected_os not in normalized_os:
            required_text = format_capability_values(raw_caps.get("os", []))
            detected_text = detected_os.upper() or "UNKNOWN"
            return build_compatibility_info(
                IncompatibilityReason.OS_INCOMPATIBLE,
                f"Requires {required_text}. Detected: {detected_text}. Override at your own risk.",
                {
                    "required_os": as_json_list(raw_caps.get("os", []) or []),
                    "detected_os": detected_os or None,
                },
                override_flag,
            )
    host_gpu: JSONDict = {}
    available_vendors: list[str] = []
    required_vendors: list[str] = []
    raw_required_gpu: list[JSONValue] = as_json_list(raw_caps.get("gpu", []))
    if normalized_gpu is not None:
        host_gpu_value = host_snapshot.get("gpu")
        host_gpu = host_gpu_value if isinstance(host_gpu_value, dict) else {}
        vendors_value = host_gpu.get("vendors")
        vendors = vendors_value if isinstance(vendors_value, list) else []
        available_vendors = [
            str(vendor_entry).strip().lower()
            for vendor_entry in vendors
            if str(vendor_entry).strip()
        ]
        required_vendors = [value for value in normalized_gpu if value != "any"]
    if _gpu_required_but_unavailable(host_gpu, normalized_gpu):
        return _build_gpu_required_result(
            raw_caps,
            raw_required_gpu,
            available_vendors,
            override_flag,
        )
    if (
        normalized_gpu is not None
        and required_vendors
        and (not any(vendor in available_vendors for vendor in required_vendors))
    ):
        return _build_gpu_required_result(
            raw_caps,
            raw_required_gpu,
            available_vendors,
            override_flag,
        )
    return build_compatibility_info(None, "", {}, False)


def _gpu_required_but_unavailable(host_gpu: JSONDict, normalized_gpu: list[str] | None) -> bool:
    if normalized_gpu is None:
        return False
    return not coerce_bool_with_recovery(
        host_gpu.get("available"),
        logger=get_logger(LOGGER_NAME),
        operation="plugins.state.manifest_compatibility.coerce_bool",
        default=False,
        recover_message="Failed to parse compatibility bool flag (non-critical).",
    )


def _build_gpu_required_result(
    raw_caps: Mapping[str, list[str]],
    raw_required_gpu: list[JSONValue],
    available_vendors: list[str],
    override_flag: bool,
) -> CompatibilityInfo:
    required_text = format_capability_values(raw_caps.get("gpu", []))
    detected_text = format_capability_values(available_vendors) if available_vendors else "NONE"
    return build_compatibility_info(
        IncompatibilityReason.GPU_REQUIRED,
        f"Requires GPU ({required_text}). Detected vendors: {detected_text}. Override to use CPU mode (may not work).",
        {
            "required_gpu": raw_required_gpu,
            "detected_vendors": as_json_list(available_vendors),
        },
        override_flag,
    )
