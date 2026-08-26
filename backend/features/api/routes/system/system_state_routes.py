"""SoAI - System state definitions routes [backend/features/api/routes/system/system_state_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.errors.exceptions import StateError
from core.serialization.json import normalize_to_json_dict
from core.state.access import AccessAction
from core.state.state_definitions import (
    STATE_ALLOWED_COLORS,
    STATE_DEFAULT_STATUS,
    build_state_definitions,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue


__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.system.get(
        "/states",
        dependencies=require_action_dependencies(AccessAction.SYSTEM_STATUS_READ),
    )
    async def get_state_definitions() -> Response:
        state_definitions = build_state_definitions()
        states: dict[str, dict[str, JSONValue]] = {}
        tag_groups: dict[str, list[str]] = {}

        for state_name, state_payload in state_definitions.items():
            name = state_payload.get("name")
            color = state_payload.get("color")
            description = state_payload.get("description")
            group = state_payload.get("group")
            raw_tags = state_payload.get("tags")

            if not isinstance(name, str):
                raise StateError(f"State definition {state_name} name must be a string")
            if not isinstance(color, str):
                raise StateError(f"State definition {state_name} color must be a string")
            if not isinstance(description, str):
                raise StateError(f"State definition {state_name} description must be a string")
            if not isinstance(group, str):
                raise StateError(f"State definition {state_name} group must be a string")

            tags: list[str] = []
            if isinstance(raw_tags, list | tuple):
                for tag in raw_tags:
                    if not isinstance(tag, str):
                        continue
                    tags.append(tag)
                    grouped = tag_groups.get(tag)
                    if grouped is None:
                        grouped = []
                        tag_groups[tag] = grouped
                    grouped.append(state_name)

            states[state_name] = {
                "name": name,
                "color": color,
                "description": description,
                "group": group,
                "tags": tags,
            }
        payload: JSONDict = {
            "default": STATE_DEFAULT_STATUS,
            "states": states,
            "allowed_colors": list(STATE_ALLOWED_COLORS),
            "tags": {tag: sorted(values) for tag, values in tag_groups.items()},
        }
        return JSONResponse(
            content=normalize_to_json_dict(
                payload, message="State definitions payload is invalid."
            ),
        )
