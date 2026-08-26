/* SoAI - Shared connection state waiters [frontend/assets/ts/core/connectionstate/waiters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortSignal } from '@core/connectionstate/internalContracts.ts';
import type { Waiter, WhenReadyOptions } from '@core/connectionstate/contracts.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { ConnectionStateState } from '@core/connectionstate/state.ts';

const whenBaseUrlReady = (state: ConnectionStateState, options: WhenReadyOptions): Promise<string> => {
    const safeOptions = isObject(options) ? options : {};
    if (isString(state.baseUrl) && state.baseUrl.length > 0) {
        return Promise.resolve(state.baseUrl);
    }

    return new Promise((resolvePromise, rejectPromise) => {
        const waiter: Waiter = {
            resolve: resolvePromise,
            reject: rejectPromise,
            cleanup: null
        };
        state.waiters.add(waiter);

        const { signal } = safeOptions;
        if (!signal || !isAbortSignal(signal)) {
            return;
        }

        if (signal.aborted) {
            state.waiters.delete(waiter);
            rejectPromise(signal.reason || new DOMException('Aborted', 'AbortError'));
            return;
        }

        const handleAbort = (): void => {
            state.waiters.delete(waiter);
            rejectPromise(signal.reason || new DOMException('Aborted', 'AbortError'));
        };

        signal.addEventListener('abort', handleAbort, { once: true });
        waiter.cleanup = () => {
            signal.removeEventListener('abort', handleAbort);
        };
    });
};

export { whenBaseUrlReady };
