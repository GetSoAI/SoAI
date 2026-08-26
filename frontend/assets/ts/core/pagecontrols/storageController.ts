/* SoAI - Shared page controls storage controller [frontend/assets/ts/core/pagecontrols/storageController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { FileExplorerPageControlState, HardwarePageControlState, LogsPageControlState, MetricsPageControlState, ModelDetailPageControlState, ModelsPageControlState, PageControlPageId, PageControlState, PageControlStates, PageSortState, PluginsPageControlState, PromptsPageControlState } from '@core/storage/types.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';

interface PageControlsStorage {
    getPageControlState(pageId: 'models'): ModelsPageControlState;
    getPageControlState(pageId: 'plugins'): PluginsPageControlState;
    getPageControlState(pageId: 'prompts'): PromptsPageControlState;
    getPageControlState(pageId: 'fileExplorer'): FileExplorerPageControlState;
    getPageControlState(pageId: 'modelDetail'): ModelDetailPageControlState;
    getPageControlState(pageId: 'logs'): LogsPageControlState;
    getPageControlState(pageId: 'metrics'): MetricsPageControlState;
    getPageControlState(pageId: 'hardware'): HardwarePageControlState;
    getPageControlState(pageId: 'osNetwork'): PageSortState;
    getPageControlState(pageId: 'osStorage'): PageSortState;
    getPageControlState(pageId: 'updates'): PageSortState;
    getPageControlState(pageId: PageControlPageId): PageControlState;
    getPageControlStates(): PageControlStates;
    setPageControlState(pageId: 'models', value: Partial<ModelsPageControlState>): void;
    setPageControlState(pageId: 'plugins', value: Partial<PluginsPageControlState>): void;
    setPageControlState(pageId: 'prompts', value: Partial<PromptsPageControlState>): void;
    setPageControlState(pageId: 'fileExplorer', value: Partial<FileExplorerPageControlState>): void;
    setPageControlState(pageId: 'modelDetail', value: Partial<ModelDetailPageControlState>): void;
    setPageControlState(pageId: 'logs', value: Partial<LogsPageControlState>): void;
    setPageControlState(pageId: 'metrics', value: Partial<MetricsPageControlState>): void;
    setPageControlState(pageId: 'hardware', value: Partial<HardwarePageControlState>): void;
    setPageControlState(pageId: 'osNetwork', value: Partial<PageSortState>): void;
    setPageControlState(pageId: 'osStorage', value: Partial<PageSortState>): void;
    setPageControlState(pageId: 'updates', value: Partial<PageSortState>): void;
    setPageControlState(pageId: PageControlPageId, value: JsonValue): void;
    setPageControlStates(value: JsonValue): void;
}

interface PageControlsStorageCandidate {
    getPageControlState?: CallableFunction;
    getPageControlStates?: CallableFunction;
    setPageControlState?: CallableFunction;
    setPageControlStates?: CallableFunction;
}

type PageControlsStorageInput = PageControlsStorageCandidate | JsonValue | null | undefined;

const isPageControlsStorage = (value: PageControlsStorageInput): value is PageControlsStorage => {
    return isObject(value) && 'getPageControlState' in value && isFunction(value.getPageControlState) && 'getPageControlStates' in value && isFunction(value.getPageControlStates) && 'setPageControlState' in value && isFunction(value.setPageControlState) && 'setPageControlStates' in value && isFunction(value.setPageControlStates);
};

const requirePageControlsStorage = (storage: PageControlsStorageInput): PageControlsStorage => {
    if (!isObject(storage) || !isPageControlsStorage(storage)) {
        throw new Error('Page controls require core.storage page control methods');
    }
    return storage;
};

export { requirePageControlsStorage };
export type { PageControlsStorage, PageControlsStorageInput };
