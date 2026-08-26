/* SoAI - Models feature manager state [frontend/assets/ts/features/models/modals/downloadmodal/manager/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireInputElement } from '@core/dom/typedElements.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { createInitialManualDiscoveryState, type ManualDiscoveryState, type ModelSearchState } from '@features/models/modals/downloadmodal/downloadModalState.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';

const getModelSearchState = (runtime: DownloadModalManagerRuntime): ModelSearchState => {
    return runtime.state['modelSearch'];
};

const getManualDiscoveryState = (runtime: DownloadModalManagerRuntime): ManualDiscoveryState => {
    if (!runtime.state['manualDiscovery']) {
        runtime.state['manualDiscovery'] = createInitialManualDiscoveryState();
    }
    return runtime.state['manualDiscovery'];
};

const resetManualDiscoveryState = (state: ManualDiscoveryState): void => {
    const nextState = createInitialManualDiscoveryState();
    state.loading = nextState.loading;
    state.loaded = nextState.loaded;
    state.promise = nextState.promise;
    state.token = nextState.token;
    state.modelsPath = nextState.modelsPath;
    state.resolvedPath = nextState.resolvedPath;
    state.error = nextState.error;
};

const getModelSearchInputValue = (runtime: DownloadModalManagerRuntime): string => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    return toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'model-search-input'), 'Download modal model-search-input', modalRoot).value);
};

export { getManualDiscoveryState, getModelSearchInputValue, getModelSearchState, resetManualDiscoveryState };
