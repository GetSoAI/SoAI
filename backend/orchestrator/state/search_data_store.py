"""SoAI - Search data storage and query operations [backend/orchestrator/state/search_data_store.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from orchestrator.state.search import perform_search, prepare_search_inputs

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("SearchDataStore",)

LOGGER_NAME = "SoAI.orchestrator.state.search_data_store"


class SearchDataStore:
    def __init__(self) -> None:
        self._logger: TraceLogger = get_logger(LOGGER_NAME)

    def search_with_data(
        self,
        query: str,
        plugin_data: Iterable[JSONDict] | None,
        model_data: dict[str, list[JSONDict]] | None,
        hardware_data: JSONDict | None,
        limit: int = 5,
    ) -> dict[str, list[JSONDict]]:
        processed_plugins, processed_models, processed_hardware = prepare_search_inputs(
            plugin_data=plugin_data,
            model_data=model_data,
            hardware_data=hardware_data,
        )
        return perform_search(
            logger=self._logger,
            query=query,
            plugin_data=processed_plugins,
            model_data=processed_models,
            hardware_data=processed_hardware,
            limit=limit,
        )
