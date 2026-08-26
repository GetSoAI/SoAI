"""SoAI - Plugin/SoAI version compatibility helpers [backend/plugins/state/version_compatibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from packaging.specifiers import SpecifierSet

from core.errors.exception_logging import log_handled_exception
from core.logging.trace import get_logger
from core.meta.versioning import NormalizedVersion, parse_semantic_version

__all__ = (
    "compute_compatible_upper_bound",
    "compute_previous_version_string",
    "determine_version_mitigation",
)

LOGGER_NAME = "SoAI.plugins.state.version_compatibility"
OPERATION_DETERMINE_VERSION_MITIGATION = (
    "plugins.state.version_compatibility.determine_version_mitigation"
)


def compute_compatible_upper_bound(
    base_version: NormalizedVersion,
) -> NormalizedVersion:
    release = list(base_version.release or ())
    if not release:
        return base_version
    upper_release: tuple[int, ...]
    if len(release) == 1:
        upper_release = (release[0] + 1,)
    else:
        prefix = list(release[:-1])
        prefix[-1] += 1
        upper_release = tuple(prefix)
    return parse_semantic_version(".".join(str(part) for part in upper_release))


def compute_previous_version_string(
    version_obj: NormalizedVersion,
) -> str | None:
    release = list(version_obj.release or ())
    for index in range(len(release) - 1, -1, -1):
        if release[index] > 0:
            release[index] -= 1
            release = release[: index + 1]
            break
    else:
        return None
    return ".".join(str(part) for part in release) if release else None


def determine_version_mitigation(
    specifier: SpecifierSet,
    current_version_obj: NormalizedVersion,
) -> tuple[str, str | None]:
    logger = get_logger(LOGGER_NAME)
    lower_bound, lower_inclusive, upper_bound, upper_inclusive = (
        None,
        False,
        None,
        False,
    )
    upper_hint_value, upper_hint_mode = (None, None)
    for item in specifier:
        operator, version_string = (item.operator, item.version)
        if operator == "!=":
            continue
        if operator == "==":
            target = parse_semantic_version(version_string)
            lower_inclusive = upper_inclusive = True
            lower_bound = target
            upper_bound = target
            upper_hint_value, upper_hint_mode = (str(target), "exact")
            break
        if operator == "~=":
            lower_compatible = parse_semantic_version(version_string)
            upper_compatible = compute_compatible_upper_bound(lower_compatible)
            if (
                lower_bound is None
                or lower_compatible > lower_bound
                or (lower_compatible == lower_bound and (not lower_inclusive))
            ):
                lower_bound, lower_inclusive = (lower_compatible, True)
            if (
                upper_bound is None
                or upper_compatible < upper_bound
                or (upper_compatible == upper_bound and upper_inclusive)
            ):
                upper_bound, upper_inclusive, upper_hint_value, upper_hint_mode = (
                    upper_compatible,
                    False,
                    version_string,
                    "lower",
                )
            continue
        version_candidate = parse_semantic_version(version_string)
        if operator == ">=":
            if (
                lower_bound is None
                or version_candidate > lower_bound
                or (version_candidate == lower_bound and (not lower_inclusive))
            ):
                lower_bound, lower_inclusive = (version_candidate, True)
        elif operator == ">":
            if lower_bound is None or version_candidate >= lower_bound:
                lower_bound, lower_inclusive = (version_candidate, False)
        elif operator == "<=":
            if (
                upper_bound is None
                or version_candidate < upper_bound
                or (version_candidate == upper_bound and (not upper_inclusive))
            ):
                upper_bound, upper_inclusive, upper_hint_value, upper_hint_mode = (
                    version_candidate,
                    True,
                    version_string,
                    "inclusive",
                )
        elif operator == "<":
            if upper_bound is None or version_candidate <= upper_bound:
                upper_bound, upper_inclusive, upper_hint_value, upper_hint_mode = (
                    version_candidate,
                    False,
                    version_string,
                    "exclusive",
                )
    if lower_bound is not None and (
        current_version_obj < lower_bound
        or (current_version_obj == lower_bound and (not lower_inclusive))
    ):
        return ("upgrade", str(lower_bound))
    if upper_bound is not None and (
        current_version_obj > upper_bound
        or (current_version_obj == upper_bound and (not upper_inclusive))
    ):
        target_display = str(upper_bound)
        if not upper_inclusive:
            if upper_hint_mode == "lower" and lower_bound is not None:
                target_display = str(lower_bound)
            elif upper_hint_value:
                try:
                    parsed_hint = parse_semantic_version(upper_hint_value)
                    if parsed_hint is not None:
                        previous_value = compute_previous_version_string(parsed_hint)
                        if previous_value:
                            target_display = previous_value
                except ValueError as version_error:
                    log_handled_exception(
                        logger,
                        version_error,
                        message="Could not parse version hint for display (non-critical).",
                        operation=OPERATION_DETERMINE_VERSION_MITIGATION,
                        details={"version_hint": upper_hint_value},
                        level="debug",
                    )
            else:
                previous_value = compute_previous_version_string(upper_bound)
                if previous_value:
                    target_display = previous_value
        return ("downgrade", target_display)
    return ("upgrade", None)
