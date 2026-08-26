/* SoAI - Shared frontend storage service page controls [frontend/assets/ts/core/storage/service/pageControls.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { applyPageControlStateUpdate, applyPageControlStatesPatch } from '@core/storage/service/pageControlMappers.ts';
import type { StorageRuntime } from '@core/storage/service/types.ts';
import type { FileExplorerPageControlState, HardwarePageControlState, LogsPageControlState, MetricsPageControlState, ModelDetailPageControlState, ModelsPageControlState, PageControlPageId, PageControlState, PageControlStates, PageSortState, PluginsPageControlState, PromptsPageControlState } from '@core/storage/types.ts';

const createStoragePageControlMethods = (core: StorageRuntime): { getPageControlState: { (pageId: 'models'): ModelsPageControlState; (pageId: 'plugins'): PluginsPageControlState; (pageId: 'prompts'): PromptsPageControlState; (pageId: 'fileExplorer'): FileExplorerPageControlState; (pageId: 'modelDetail'): ModelDetailPageControlState; (pageId: 'logs'): LogsPageControlState; (pageId: 'metrics'): MetricsPageControlState; (pageId: 'hardware'): HardwarePageControlState; (pageId: 'osNetwork'): PageSortState; (pageId: 'osStorage'): PageSortState; (pageId: 'updates'): PageSortState }; getPageControlStates: () => PageControlStates; setPageControlState: (pageId: PageControlPageId, patch: JsonValue) => void; setPageControlStates: (patch: JsonValue) => void } => {
    function getPageControlState(pageId: 'models'): ModelsPageControlState;
    function getPageControlState(pageId: 'plugins'): PluginsPageControlState;
    function getPageControlState(pageId: 'prompts'): PromptsPageControlState;
    function getPageControlState(pageId: 'fileExplorer'): FileExplorerPageControlState;
    function getPageControlState(pageId: 'modelDetail'): ModelDetailPageControlState;
    function getPageControlState(pageId: 'logs'): LogsPageControlState;
    function getPageControlState(pageId: 'metrics'): MetricsPageControlState;
    function getPageControlState(pageId: 'hardware'): HardwarePageControlState;
    function getPageControlState(pageId: 'osNetwork'): PageSortState;
    function getPageControlState(pageId: 'osStorage'): PageSortState;
    function getPageControlState(pageId: 'updates'): PageSortState;
    function getPageControlState(pageId: PageControlPageId): PageControlState {
        return core.clone(core.state.cache.filters.pageControls[pageId]);
    }

    const getPageControlStates = (): PageControlStates => core.clone(core.state.cache.filters.pageControls);

    const setPageControlState = (pageId: PageControlPageId, patch: JsonValue): void => {
        applyPageControlStateUpdate(pageId, patch, core.state.cache.filters.pageControls);
        terminateHandledPromise(core.queuePersist('filters'));
    };

    const setPageControlStates = (patch: JsonValue): void => {
        applyPageControlStatesPatch(patch, core.state.cache.filters.pageControls);
        terminateHandledPromise(core.queuePersist('filters'));
    };

    return {
        getPageControlState,
        getPageControlStates,
        setPageControlState,
        setPageControlStates
    };
};

export { createStoragePageControlMethods };
