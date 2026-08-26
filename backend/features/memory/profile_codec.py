"""SoAI - Memory profile codec [backend/features/memory/profile_codec.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "PROFILE_FIELD_NAMES",
    "USER_PROFILE_ENTITY_NAME",
    "USER_PROFILE_ENTITY_TYPE",
    "USER_PROFILE_SOURCE",
    "build_profile_form",
    "build_profile_observations",
)

USER_PROFILE_ENTITY_NAME = "user_profile"
USER_PROFILE_ENTITY_TYPE = "person"
USER_PROFILE_SOURCE = "chat_memory_onboarding"
PROFILE_FIELD_NAMES: tuple[str, ...] = (
    "preferred_name",
    "assistant_name",
    "role_background",
    "current_goals",
    "preferences",
    "dislikes_to_avoid",
    "communication_style",
    "recurring_tools_projects",
    "extra_notes",
)
_OBSERVATION_FIELD_PREFIXES: tuple[tuple[str, str], ...] = (
    ("role_background", "Role/background:"),
    ("current_goals", "Current goals:"),
    ("preferences", "Preferences:"),
    ("dislikes_to_avoid", "Avoid:"),
    ("communication_style", "Preferred communication style:"),
    ("recurring_tools_projects", "Recurring tools/projects context:"),
    ("extra_notes", "Extra notes:"),
)


def build_profile_observations(payload: JSONDict) -> list[str]:
    observations: list[str] = []
    for field_name, prefix in _OBSERVATION_FIELD_PREFIXES:
        normalized_value = coerce_optional_trimmed_str(payload.get(field_name))
        if normalized_value is not None:
            observations.append(f"{prefix} {normalized_value}")
    return observations


def build_profile_form(
    entries: list[JSONDict],
    *,
    preferred_name: str | None,
    assistant_name: str | None,
) -> JSONDict:
    profile_form = _extract_profile_observation_values(entries)
    for field_name in PROFILE_FIELD_NAMES:
        if field_name not in profile_form:
            profile_form[field_name] = None
    profile_form["preferred_name"] = preferred_name
    profile_form["assistant_name"] = assistant_name
    return profile_form


def _extract_profile_observation_values(entries: list[JSONDict]) -> JSONDict:
    values: JSONDict = {}
    for entry in entries:
        entity = entry.get("entity")
        if not isinstance(entity, dict) or entity.get("name") != USER_PROFILE_ENTITY_NAME:
            continue
        observations = entry.get("observations")
        if not isinstance(observations, list):
            continue
        for observation in observations:
            if not isinstance(observation, dict):
                continue
            if observation.get("source") != USER_PROFILE_SOURCE:
                continue
            content = observation.get("content")
            if not isinstance(content, str):
                continue
            for field_name, prefix in _OBSERVATION_FIELD_PREFIXES:
                marker = f"{prefix} "
                if content.startswith(marker):
                    if field_name not in values:
                        values[field_name] = content[len(marker) :]
    return values
