/* SoAI - Models feature download modal state [frontend/assets/ts/features/models/modals/downloadmodal/downloadModalState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { ModelSearchResults } from '@features/models/modals/downloadmodal/modelSearchTypes.ts';

interface ModelSearchState {
    results: ModelSearchResults;
    loading: boolean;
    abortController: AbortController | null;
    token: symbol | null;
    selectedIndex: number | null;
    plugin: string;
}

interface ManualDiscoveryState {
    loading: boolean;
    loaded: boolean;
    promise: Promise<ManualDiscoveryState | null> | null;
    token: symbol | null;
    modelsPath: string;
    resolvedPath: string;
    error: Error | null;
}

interface DownloadModalState {
    activeDownloadSignatures: Set<string>;
    modelSearch: ModelSearchState;
    manualDiscovery: ManualDiscoveryState;
    isCreatingProvider: boolean;
    acceptedCatalogMutation: boolean;
    currentPlugin?: PluginRecord | null;
}

const createInitialManualDiscoveryState = (): ManualDiscoveryState => {
    return {
        loading: false,
        loaded: false,
        promise: null,
        token: null,
        modelsPath: '',
        resolvedPath: '',
        error: null
    };
};

const createInitialDownloadModalState = (): DownloadModalState => {
    return {
        activeDownloadSignatures: new Set<string>(),
        modelSearch: {
            results: [],
            loading: false,
            abortController: null,
            token: null,
            selectedIndex: null,
            plugin: ''
        },
        manualDiscovery: createInitialManualDiscoveryState(),
        isCreatingProvider: false,
        acceptedCatalogMutation: false
    };
};

export { createInitialDownloadModalState, createInitialManualDiscoveryState };
export type { DownloadModalState, ModelSearchState, ManualDiscoveryState };
