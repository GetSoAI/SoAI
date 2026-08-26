/* SoAI - Status manager initialization and reset [frontend/assets/ts/core/state/statusmanager/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DEFAULT_STATUS_CONFIG } from '@core/state/constants.ts';
import { deriveDefinitions } from '@core/state/statusNormalization.ts';
import type { StatusManagerState } from '@core/state/statusmanager/internalContracts.ts';

const createInitialState = (): StatusManagerState => {
    return {
        definitions: deriveDefinitions(),
        defaultStatus: DEFAULT_STATUS_CONFIG.defaultStatus,
        allowedColors: Array.from(DEFAULT_STATUS_CONFIG.allowedColors),
        activeStatuses: new Set(DEFAULT_STATUS_CONFIG.tags.active),
        errorStatuses: new Set(DEFAULT_STATUS_CONFIG.tags.error),
        transitionStatuses: new Set(DEFAULT_STATUS_CONFIG.tags.transition)
    };
};

const cloneStatusSet = (source: Set<string>): Set<string> => {
    return new Set(source);
};

const resetState = (state: StatusManagerState): void => {
    const nextState = createInitialState();
    state.definitions = nextState.definitions;
    state.defaultStatus = nextState.defaultStatus;
    state.allowedColors = nextState.allowedColors;
    state.activeStatuses = cloneStatusSet(nextState.activeStatuses);
    state.errorStatuses = cloneStatusSet(nextState.errorStatuses);
    state.transitionStatuses = cloneStatusSet(nextState.transitionStatuses);
};

export { createInitialState, resetState };
