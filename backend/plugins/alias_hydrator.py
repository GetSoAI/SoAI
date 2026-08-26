"""SoAI - Plugin alias hydration service [backend/plugins/alias_hydrator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import TraceLogger
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.serialization.json_parsing import parse_json_value
from core.state.state_names import (
    PLUGIN_STATE_ABSENT,
    PLUGIN_STATE_DELETING,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_REMOVING_BACKEND,
)
from core.types.json import is_json_value
from core.validation.strings import coerce_trimmed_str_or_empty
from plugins.identity import normalize_plugin_lookup_key

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "PluginAliasHydrator",
    "PluginAliasHydratorDependencies",
)

OPERATION_PLUGIN_TYPES_HYDRATE = "plugin_types.hydrate"
OPERATION_PLUGIN_TYPES_TRY_CLEANUP_ABSENT_PLUGIN_RECORD = (
    "plugin_types.try_cleanup_absent_plugin_record"
)


TRANSIENT_PLUGIN_STATES = frozenset(
    {
        PLUGIN_STATE_NOT_DETECTED,
        PLUGIN_STATE_ABSENT,
        PLUGIN_STATE_DELETING,
        PLUGIN_STATE_REMOVING_BACKEND,
    },
)


@dataclass(frozen=True, slots=True)
class PluginAliasHydratorDependencies:
    database_plugins: DatabasePluginsProtocol
    logger: TraceLogger

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginAliasHydratorDependencies",
            database_plugins=self.database_plugins,
            logger=self.logger,
        )


class PluginAliasHydrator:
    def __init__(self, deps: PluginAliasHydratorDependencies) -> None:
        self._deps = deps

    async def _try_cleanup_absent_plugin_record(
        self,
        plugin_name: str,
        loaded_plugin_surfaces: dict[str, tuple[JSONDict, str]],
    ) -> None:
        normalized_name = normalize_plugin_lookup_key(plugin_name)
        if normalized_name is None:
            return
        if normalized_name in loaded_plugin_surfaces:
            return
        try:
            deleted = await self._deps.database_plugins.permanently_delete_plugin_record(
                normalized_name,
            )
            if deleted:
                self._deps.logger.debug(
                    "Deleted stale plugin database record for '%s' (plugin file missing).",
                    normalized_name,
                )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                self._deps.logger,
                exception,
                message="Failed to delete ABSENT plugin record (non-critical).",
                operation=OPERATION_PLUGIN_TYPES_TRY_CLEANUP_ABSENT_PLUGIN_RECORD,
                level="debug",
                details={"plugin_name": normalized_name},
            )

    @staticmethod
    def _commit_alias(
        alias_map: dict[str, str],
        alias: JSONValue,
        canonical: str,
        *,
        override: bool,
    ) -> None:
        canonical_name = canonical.strip()
        if not canonical_name:
            return
        normalized_alias = normalize_plugin_lookup_key(alias)
        if normalized_alias is None:
            return
        if override or normalized_alias not in alias_map:
            alias_map[normalized_alias] = canonical_name

    async def hydrate(
        self,
        loaded_plugin_surfaces: dict[str, tuple[JSONDict, str]],
    ) -> tuple[dict[str, str] | None, set[str] | None, dict[str, str]]:
        alias_map_db: dict[str, str] = {}
        known_plugins_db: set[str] = set()
        display_cache: dict[str, str] = {}
        try:
            database_plugins = await self._deps.database_plugins.get_all_plugins()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                self._deps.logger,
                exception,
                message="Could not hydrate alias map from database (non-critical).",
                operation=OPERATION_PLUGIN_TYPES_HYDRATE,
                level="debug",
            )
            return (None, None, display_cache)
        for record in database_plugins:
            plugin_name = record.get("plugin_name")
            if not plugin_name or not isinstance(plugin_name, str):
                continue
            plugin_state = record.get("state")
            if plugin_state in TRANSIENT_PLUGIN_STATES:
                if plugin_state == PLUGIN_STATE_ABSENT:
                    await self._try_cleanup_absent_plugin_record(
                        plugin_name,
                        loaded_plugin_surfaces,
                    )
                else:
                    self._deps.logger.trace(
                        "Skipping plugin '%s' from alias map (transient state: %s)",
                        plugin_name,
                        plugin_state,
                    )
                continue
            normalized_name = normalize_plugin_lookup_key(plugin_name)
            if normalized_name is None:
                continue
            known_plugins_db.add(normalized_name)
            self._commit_alias(alias_map_db, normalized_name, normalized_name, override=True)
            display_name = record.get("name")
            if isinstance(display_name, str) and display_name.strip():
                normalized_display_name = display_name.strip()
                display_cache[normalized_name] = normalized_display_name
                self._commit_alias(
                    alias_map_db,
                    normalized_display_name,
                    normalized_name,
                    override=False,
                )
            raw_aliases = record.get("aliases")
            alias_list: list[JSONValue] = []
            if isinstance(raw_aliases, str):
                try:
                    parsed = parse_json_value(raw_aliases)
                    if isinstance(parsed, list):
                        alias_list = [item for item in parsed if is_json_value(item)]
                except ValidationError:
                    alias_list = []
            elif isinstance(raw_aliases, list):
                alias_list = [item for item in raw_aliases if is_json_value(item)]
            for alias in alias_list:
                self._commit_alias(alias_map_db, alias, normalized_name, override=False)
        for name, (plugin_data, _) in loaded_plugin_surfaces.items():
            canonical = coerce_trimmed_str_or_empty(name)
            if not canonical:
                continue
            self._commit_alias(alias_map_db, canonical, canonical, override=True)
            known_plugins_db.add(canonical)
            aliases_value = plugin_data.get("aliases")
            if isinstance(aliases_value, list | tuple | set | frozenset):
                for alias in aliases_value:
                    self._commit_alias(alias_map_db, alias, canonical, override=False)
        return (alias_map_db, known_plugins_db, display_cache)
