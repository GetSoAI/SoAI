/* SoAI - Shared connection state internal contracts [frontend/assets/ts/core/connectionstate/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import type { StateManager } from '@core/connectionstate/contracts.ts';

const isAbortSignal = <T>(value: T): value is T & AbortSignal => {
    if (!isObject(value)) {
        return false;
    }
    return 'addEventListener' in value && isFunction(value.addEventListener) && 'removeEventListener' in value && isFunction(value.removeEventListener) && 'aborted' in value && typeof value.aborted === 'boolean';
};

const isStateManager = <T>(value: T): value is T & StateManager => {
    if (!isObject(value)) {
        return false;
    }
    return 'getTabState' in value && isFunction(value.getTabState) && 'subscribeTabState' in value && isFunction(value.subscribeTabState);
};

export { isAbortSignal, isStateManager };
